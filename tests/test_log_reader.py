from __future__ import annotations

import pytest

from mt5_mcp import log_reader


def test_read_log_returns_tail(tmp_path):
    log_dir = tmp_path / "Logs"
    log_dir.mkdir()
    log_file = log_dir / "20240101.log"
    log_file.write_text("\n".join(f"line {i}" for i in range(1, 11)), encoding="utf-8")

    result = log_reader.read_log(date="20240101", lines=3, log_dir=str(log_dir))
    assert result["total_lines"] == 10
    assert result["returned_lines"] == 3
    assert result["lines"] == ["line 8", "line 9", "line 10"]


def test_read_log_missing_file_raises(tmp_path):
    log_dir = tmp_path / "Logs"
    log_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        log_reader.read_log(date="19990101", log_dir=str(log_dir))


def test_list_available_logs(tmp_path):
    log_dir = tmp_path / "Logs"
    log_dir.mkdir()
    (log_dir / "20240101.log").write_text("a", encoding="utf-8")
    (log_dir / "20240102.log").write_text("b", encoding="utf-8")
    dates = log_reader.list_available_logs(log_dir=str(log_dir))
    assert dates == ["20240101", "20240102"]


def test_list_available_logs_missing_dir_returns_empty(tmp_path):
    dates = log_reader.list_available_logs(log_dir=str(tmp_path / "does_not_exist"))
    assert dates == []


def test_experts_kind_uses_different_subdir(fake_mt5, monkeypatch):
    monkeypatch.setenv("MT5_MCP_LOG_SOURCE_DIR", "")
    monkeypatch.delenv("MT5_MCP_LOG_SOURCE_DIR", raising=False)
    log_dir = log_reader._resolve_log_dir(kind="experts")
    assert str(log_dir).endswith("MQL5/Logs") or str(log_dir).endswith("MQL5\\Logs")
