"""MQL5 workspace tools and the shared workspace configuration used by the file tools.

The "workspace" is the directory that holds MQL5 sources - normally the terminal's
`MQL5` data folder (Experts/Indicators/Scripts/Include subtrees), pointed at via
`MT5_MCP_WORKSPACE_DIR`. Every path the file tools touch is confined inside this root
by `paths.resolve_within`, so no tool can read or write outside it.

This module also owns the cross-cutting locations (`backups/`, `drafts/`) and the set
of file extensions the bridge is willing to manage, so `mql5_files.py` imports them
from here rather than redefining them.
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

from .paths import env_base_dir, resolve_within
from .utils import new_id, utcnow_iso

# Source files the bridge will manage. Deliberately limited to MQL5 sources, project
# files, tester set/config files, and report/export formats - never executables.
ALLOWED_MQL5_SUFFIXES: tuple[str, ...] = (
    ".mq5",
    ".mq4",
    ".mqh",
    ".mqproj",
    ".set",
    ".ini",
    ".txt",
    ".csv",
    ".htm",
    ".html",
    ".tpl",
    ".json",
)

# Subfolders of a standard MQL5 data folder, by source kind.
_KIND_DIRS = {
    "experts": "Experts",
    "indicators": "Indicators",
    "scripts": "Scripts",
    "includes": "Include",
}

_KIND_SUFFIXES = {
    "experts": (".mq5", ".mq4", ".ex5", ".ex4"),
    "indicators": (".mq5", ".mq4", ".ex5", ".ex4"),
    "scripts": (".mq5", ".mq4", ".ex5", ".ex4"),
    "includes": (".mqh",),
}


def workspace_root() -> Path:
    """The MQL5 workspace root. Defaults to `./workspace` when MT5_MCP_WORKSPACE_DIR is unset."""
    return env_base_dir("MT5_MCP_WORKSPACE_DIR", "workspace")


def backups_dir() -> Path:
    return env_base_dir("MT5_MCP_BACKUPS_DIR", "backups")


def drafts_dir() -> Path:
    return env_base_dir("MT5_MCP_DRAFTS_DIR", "drafts")


def resolve_source(path: str, *, must_exist: bool = False) -> Path:
    """Resolve a workspace-relative path, confined to the workspace root."""
    return resolve_within(workspace_root(), path, allowed_suffixes=ALLOWED_MQL5_SUFFIXES, must_exist=must_exist)


# --- Tools -------------------------------------------------------------------


def detect_data_folder() -> dict[str, Any]:
    """Report the configured/likely MT5 Data Folder. Auto-detection needs Windows + MT5."""
    root = workspace_root()
    configured = root if root.exists() else None
    result: dict[str, Any] = {
        "workspace_root": str(root),
        "exists": root.exists(),
        "configured_via": "MT5_MCP_WORKSPACE_DIR" if configured else "default ./workspace",
    }
    if sys.platform != "win32":
        result["auto_detect"] = "UNSUPPORTED_IN_THIS_ENVIRONMENT"
        result["note"] = (
            "Automatic MT5 Data Folder detection requires Windows next to a running terminal. "
            "Set MT5_MCP_WORKSPACE_DIR to the terminal's MQL5 folder to use the file tools."
        )
    return result


def show_status() -> dict[str, Any]:
    """Summarise the workspace: root, existence, and counts per source kind."""
    root = workspace_root()
    status: dict[str, Any] = {"workspace_root": str(root), "exists": root.exists(), "counts": {}}
    if not root.exists():
        status["note"] = "Workspace root does not exist yet; set MT5_MCP_WORKSPACE_DIR or create it."
        return status
    for kind in _KIND_DIRS:
        status["counts"][kind] = len(_list_kind(kind))
    status["backups_dir"] = str(backups_dir())
    status["drafts_dir"] = str(drafts_dir())
    return status


def _list_kind(kind: str) -> list[str]:
    root = workspace_root()
    suffixes = _KIND_SUFFIXES[kind]
    sub = root / _KIND_DIRS[kind]
    search_root = sub if sub.exists() else root
    if not search_root.exists():
        return []
    matches = [
        str(p.relative_to(root))
        for p in search_root.rglob("*")
        if p.is_file() and p.suffix.lower() in suffixes
    ]
    return sorted(matches)


def list_sources(kind: str) -> dict[str, Any]:
    """List source files of `kind` (experts/indicators/scripts/includes), relative to root."""
    if kind not in _KIND_DIRS:
        raise ValueError(f"Unknown source kind '{kind}'. Expected one of: {', '.join(_KIND_DIRS)}.")
    return {"kind": kind, "root": str(workspace_root()), "files": _list_kind(kind)}


def snapshot(label: str | None = None) -> dict[str, Any]:
    """Create a zip snapshot of the whole workspace under the backups directory.

    This is a safe, read-only-of-source operation: it copies sources into a new zip and
    never modifies the workspace. Restoring is a separate, approval-gated tool.
    """
    root = workspace_root()
    if not root.exists():
        raise FileNotFoundError(f"Workspace root does not exist: {root}")
    out_dir = backups_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_id = new_id("snap")
    safe_label = (label or "snapshot").replace("/", "_").replace("\\", "_")
    archive = out_dir / f"{snap_id}__{safe_label}.zip"

    files: list[str] = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in ALLOWED_MQL5_SUFFIXES:
                rel = p.relative_to(root)
                zf.write(p, str(rel))
                files.append(str(rel))
    return {
        "snapshot_id": snap_id,
        "archive": str(archive),
        "created_at": utcnow_iso(),
        "file_count": len(files),
        "files": files,
    }


def restore_snapshot(archive: str, *, overwrite: bool = True) -> dict[str, Any]:
    """Restore a workspace snapshot zip back into the workspace root (mutating; approval-gated)."""
    out_dir = backups_dir()
    archive_path = resolve_within(out_dir, archive, allowed_suffixes=(".zip",), must_exist=True)
    root = workspace_root()
    root.mkdir(parents=True, exist_ok=True)

    restored: list[str] = []
    with zipfile.ZipFile(archive_path, "r") as zf:
        for member in zf.namelist():
            target = resolve_within(root, member, allowed_suffixes=ALLOWED_MQL5_SUFFIXES)
            if target.exists() and not overwrite:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            restored.append(member)
    return {"archive": str(archive_path), "restored_count": len(restored), "restored": restored}
