from __future__ import annotations

import pytest

from mt5_mcp import mql5_files
from mt5_mcp.paths import PathConfinementError


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "Experts").mkdir()
    monkeypatch.setenv("MT5_MCP_WORKSPACE_DIR", str(root))
    monkeypatch.setenv("MT5_MCP_BACKUPS_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("MT5_MCP_DRAFTS_DIR", str(tmp_path / "drafts"))
    return root


def _seed(root, rel="Experts/EA.mq5", content="void OnTick(){}\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return rel


def test_read_returns_content_and_hash(workspace):
    rel = _seed(workspace)
    out = mql5_files.read(rel)
    assert "OnTick" in out["content"]
    assert out["sha256"]


def test_diff_does_not_write(workspace):
    rel = _seed(workspace)
    out = mql5_files.diff(rel, "void OnTick(){return;}\n")
    assert out["has_changes"]
    assert "OnTick" in out["diff"]
    # original unchanged
    assert "return" not in (workspace / rel).read_text()


def test_write_draft_writes_to_drafts_not_source(workspace, tmp_path):
    rel = _seed(workspace)
    out = mql5_files.write_draft(rel, "// draft\n")
    assert str(tmp_path / "drafts") in out["draft_path"]
    assert (workspace / rel).read_text() == "void OnTick(){}\n"


def test_create_then_revert(workspace):
    out = mql5_files.create("Experts/New.mq5", "// new\n")
    assert (workspace / "Experts/New.mq5").exists()
    assert out["rollback_id"]
    mql5_files.revert_patch(out["rollback_id"])
    assert not (workspace / "Experts/New.mq5").exists()


def test_create_existing_raises(workspace):
    rel = _seed(workspace)
    with pytest.raises(FileExistsError):
        mql5_files.create(rel, "x")


def test_update_backs_up_and_diffs(workspace):
    rel = _seed(workspace)
    out = mql5_files.update(rel, "void OnTick(){/*v2*/}\n")
    assert out["backup_path"]
    assert "v2" in (workspace / rel).read_text()
    assert out["diff"]


def test_apply_patch_then_revert_restores_original(workspace):
    rel = _seed(workspace, content="int x = 1;\n")
    out = mql5_files.apply_patch(rel, "x = 1", "x = 2")
    assert "x = 2" in (workspace / rel).read_text()
    mql5_files.revert_patch(out["rollback_id"])
    assert "x = 1" in (workspace / rel).read_text()


def test_apply_patch_missing_target_raises(workspace):
    rel = _seed(workspace)
    with pytest.raises(ValueError):
        mql5_files.apply_patch(rel, "NOT_PRESENT", "y")


def test_delete_then_revert_restores(workspace):
    rel = _seed(workspace, content="keep me\n")
    out = mql5_files.delete(rel)
    assert not (workspace / rel).exists()
    mql5_files.revert_patch(out["rollback_id"])
    assert (workspace / rel).read_text() == "keep me\n"


def test_rename_then_revert(workspace):
    rel = _seed(workspace)
    out = mql5_files.rename(rel, "Experts/Renamed.mq5")
    assert (workspace / "Experts/Renamed.mq5").exists()
    assert not (workspace / rel).exists()
    mql5_files.revert_patch(out["rollback_id"])
    assert (workspace / rel).exists()


def test_backup_and_restore_round_trip(workspace):
    rel = _seed(workspace, content="v1\n")
    bk = mql5_files.backup(rel)
    mql5_files.update(rel, "v2\n")
    assert (workspace / rel).read_text() == "v2\n"
    # backup_path is absolute; restore confines to backups dir using the file name
    from pathlib import Path

    mql5_files.restore(rel, Path(bk["backup_path"]).name)
    assert (workspace / rel).read_text() == "v1\n"


def test_path_traversal_is_rejected(workspace):
    with pytest.raises(PathConfinementError):
        mql5_files.read("../outside.mq5")


def test_disallowed_suffix_is_rejected(workspace):
    with pytest.raises(PathConfinementError):
        mql5_files.create("Experts/evil.exe", "x")
