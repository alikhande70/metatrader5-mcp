"""MQL5 file tools: read / diff / draft (safe) and mutate (approval + backup + rollback).

Read, diff, draft, and backup are safe: they never modify a real source file. The
mutating tools (create/update/apply_patch/delete/rename/restore/revert_patch) are
classified FILE_CHANGE in the policy manifest, so action_router requires human approval
before they run. Independently, each mutation here also:

  - takes a backup of the prior state,
  - writes a rollback-metadata record so the change can be undone, and
  - returns a unified diff of what changed.

Every path is confined to the workspace root via workspace_tools.resolve_source.
"""

from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
from typing import Any

from . import workspace_tools as ws
from .paths import resolve_within
from .utils import get_logger, new_id, utcnow_iso

logger = get_logger(__name__)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-16")


def _unified_diff(old: str, new: str, rel: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
    )
    return "".join(diff)


def _backup_state(path: Path, rel: str) -> str | None:
    """Copy the current file content into the backups dir. Returns the backup file path, or None if absent."""
    if not path.exists():
        return None
    out_dir = ws.backups_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    flat = rel.replace("/", "__").replace("\\", "__")
    backup_path = out_dir / f"{new_id('bak')}__{flat}"
    backup_path.write_text(_read_text(path), encoding="utf-8")
    return str(backup_path)


def _write_rollback(op: str, rel: str, backup_path: str | None, new_sha: str | None) -> str:
    """Persist a rollback record and return its id (used by revert_patch / restore)."""
    rollback_id = new_id("rb")
    out_dir = ws.backups_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "rollback_id": rollback_id,
        "op": op,
        "path": rel,
        "backup_path": backup_path,
        "new_sha256": new_sha,
        "created_at": utcnow_iso(),
    }
    (out_dir / f"rollback_{rollback_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return rollback_id


def _mutation_result(op: str, rel: str, old: str, new: str, *, backup_path: str | None) -> dict[str, Any]:
    rollback_id = _write_rollback(op, rel, backup_path, _sha256(new) if new else None)
    return {
        "op": op,
        "path": rel,
        "diff": _unified_diff(old, new, rel),
        "backup_path": backup_path,
        "rollback_id": rollback_id,
        "sha256": _sha256(new) if new else None,
        "applied": True,
    }


# --- Safe tools (Level 0 / 1) ------------------------------------------------


def read(path: str) -> dict[str, Any]:
    target = ws.resolve_source(path, must_exist=True)
    content = _read_text(target)
    return {
        "path": path,
        "absolute_path": str(target),
        "content": content,
        "lines": content.count("\n") + (1 if content and not content.endswith("\n") else 0),
        "sha256": _sha256(content),
    }


def diff(path: str, new_content: str) -> dict[str, Any]:
    """Unified diff between the current file (or empty, if new) and `new_content`. No write."""
    target = ws.resolve_source(path)
    old = _read_text(target) if target.exists() else ""
    patch = _unified_diff(old, new_content, path)
    return {"path": path, "exists": target.exists(), "has_changes": bool(patch), "diff": patch}


def write_draft(path: str, content: str) -> dict[str, Any]:
    """Write `content` to the drafts directory (never the real source). Returns the draft path + diff."""
    drafts = ws.drafts_dir()
    draft_path = resolve_within(drafts, path, allowed_suffixes=ws.ALLOWED_MQL5_SUFFIXES)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(content, encoding="utf-8")

    source = ws.resolve_source(path)
    old = _read_text(source) if source.exists() else ""
    return {
        "path": path,
        "draft_path": str(draft_path),
        "diff_vs_source": _unified_diff(old, content, path),
        "note": "Draft written to the drafts directory. Use mql5_file_apply_patch/update to apply it (approval required).",
    }


def backup(path: str) -> dict[str, Any]:
    """Copy the current source file into the backups directory. Safe; does not modify the source."""
    target = ws.resolve_source(path, must_exist=True)
    backup_path = _backup_state(target, path)
    return {"path": path, "backup_path": backup_path, "created_at": utcnow_iso()}


# --- Mutating tools (Level 2: approval-gated by action_router) ---------------


def create(path: str, content: str) -> dict[str, Any]:
    target = ws.resolve_source(path)
    if target.exists():
        raise FileExistsError(f"File already exists: {path}. Use mql5_file_update to change it.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    logger.info("Created file %s", target)
    return _mutation_result("create", path, "", content, backup_path=None)


def update(path: str, content: str) -> dict[str, Any]:
    target = ws.resolve_source(path, must_exist=True)
    old = _read_text(target)
    backup_path = _backup_state(target, path)
    target.write_text(content, encoding="utf-8")
    logger.info("Updated file %s", target)
    return _mutation_result("update", path, old, content, backup_path=backup_path)


def apply_patch(path: str, find: str, replace: str, *, count: int = 0) -> dict[str, Any]:
    """Apply a find/replace patch to a file (count=0 replaces all occurrences)."""
    target = ws.resolve_source(path, must_exist=True)
    old = _read_text(target)
    if find not in old:
        raise ValueError(f"Patch target text not found in {path}; nothing applied.")
    new = old.replace(find, replace) if count == 0 else old.replace(find, replace, count)
    backup_path = _backup_state(target, path)
    target.write_text(new, encoding="utf-8")
    logger.info("Applied patch to %s", target)
    return _mutation_result("apply_patch", path, old, new, backup_path=backup_path)


def delete(path: str) -> dict[str, Any]:
    target = ws.resolve_source(path, must_exist=True)
    old = _read_text(target)
    backup_path = _backup_state(target, path)
    target.unlink()
    logger.info("Deleted file %s", target)
    return _mutation_result("delete", path, old, "", backup_path=backup_path)


def rename(path: str, new_path: str) -> dict[str, Any]:
    src = ws.resolve_source(path, must_exist=True)
    dst = ws.resolve_source(new_path)
    if dst.exists():
        raise FileExistsError(f"Destination already exists: {new_path}.")
    content = _read_text(src)
    backup_path = _backup_state(src, path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    logger.info("Renamed %s -> %s", src, dst)
    rollback_id = _write_rollback("rename", f"{path} -> {new_path}", backup_path, _sha256(content))
    return {
        "op": "rename",
        "path": path,
        "new_path": new_path,
        "backup_path": backup_path,
        "rollback_id": rollback_id,
        "applied": True,
    }


def restore(path: str, backup_path: str) -> dict[str, Any]:
    """Restore a file from a backup produced by a prior backup/mutation."""
    backup_file = resolve_within(ws.backups_dir(), backup_path, must_exist=True)
    target = ws.resolve_source(path)
    old = _read_text(target) if target.exists() else ""
    new = _read_text(backup_file)
    pre_backup = _backup_state(target, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new, encoding="utf-8")
    logger.info("Restored %s from %s", target, backup_file)
    return _mutation_result("restore", path, old, new, backup_path=pre_backup)


def revert_patch(rollback_id: str) -> dict[str, Any]:
    """Undo a prior mutation using its rollback record."""
    record_path = resolve_within(ws.backups_dir(), f"rollback_{rollback_id}.json", allowed_suffixes=(".json",), must_exist=True)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    rel = record["path"]
    backup_path = record.get("backup_path")

    if rel and " -> " in rel and record.get("op") == "rename":
        # Reverse the rename.
        orig, renamed = (s.strip() for s in rel.split("->", 1))
        renamed_target = ws.resolve_source(renamed, must_exist=True)
        orig_target = ws.resolve_source(orig)
        renamed_target.rename(orig_target)
        return {"op": "revert_rename", "restored_path": orig, "rollback_id": rollback_id, "applied": True}

    target = ws.resolve_source(rel)
    old = _read_text(target) if target.exists() else ""
    if backup_path is None:
        # The op created the file; reverting means deleting it.
        if target.exists():
            target.unlink()
        return {"op": "revert_create", "path": rel, "rollback_id": rollback_id, "applied": True, "diff": _unified_diff(old, "", rel)}

    new = _read_text(Path(backup_path))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new, encoding="utf-8")
    return {"op": "revert", "path": rel, "rollback_id": rollback_id, "applied": True, "diff": _unified_diff(old, new, rel)}
