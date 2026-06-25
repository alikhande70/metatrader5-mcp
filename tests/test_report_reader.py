from __future__ import annotations

import pytest

from mt5_mcp import report_reader
from mt5_mcp.report_reader import ReportPathError

SAMPLE_REPORT_HTML = """
<html><body>
<table>
<tr><td class=hdr colspan=2>Strategy Tester Report</td></tr>
<tr><td>Total Net Profit:</td><td>2099.42</td><td>Balance Drawdown Absolute:</td><td>0.00</td></tr>
<tr><td>Profit Factor:</td><td>1.57</td><td>Expected Payoff:</td><td>4.20</td></tr>
<tr><td>Total Trades:</td><td>500</td></tr>
</table>
</body></html>
"""


def test_read_strategy_report_parses_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    (tmp_path / "ReportTester.html").write_text(SAMPLE_REPORT_HTML, encoding="utf-8")

    result = report_reader.read_strategy_report("ReportTester.html")

    assert result["summary"]["Total Net Profit"] == "2099.42"
    assert result["summary"]["Profit Factor"] == "1.57"
    assert result["summary"]["Total Trades"] == "500"
    assert len(result["raw_rows"]) >= 3


def test_valid_report_under_reports_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    (tmp_path / "report.html").write_text(SAMPLE_REPORT_HTML, encoding="utf-8")

    result = report_reader.read_strategy_report("report.html")
    assert result["summary"]["Total Trades"] == "500"


def test_valid_report_in_subdirectory_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    sub = tmp_path / "2024"
    sub.mkdir()
    (sub / "report.htm").write_text(SAMPLE_REPORT_HTML, encoding="utf-8")

    result = report_reader.read_strategy_report("2024/report.htm")
    assert result["summary"]["Total Trades"] == "500"


def test_missing_report_raises_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        report_reader.read_strategy_report("missing.html")


def test_missing_report_message_lists_available_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    (tmp_path / "report1.html").write_text(SAMPLE_REPORT_HTML, encoding="utf-8")
    (tmp_path / "report2.htm").write_text(SAMPLE_REPORT_HTML, encoding="utf-8")

    with pytest.raises(FileNotFoundError) as exc_info:
        report_reader.read_strategy_report("missing.html")
    msg = str(exc_info.value)
    assert "report1.html" in msg
    assert "report2.htm" in msg
    assert str(tmp_path) in msg
    assert "MT5_MCP_REPORTS_DIR" in msg


def test_missing_report_message_with_no_reports_present(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError) as exc_info:
        report_reader.read_strategy_report("missing.html")
    msg = str(exc_info.value)
    assert "No .html/.htm reports found" in msg


def test_absolute_path_outside_reports_dir_is_rejected(tmp_path, monkeypatch):
    # Reports dir is a subdir; an absolute path to a sensitive file elsewhere
    # must be rejected even though the file exists.
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(reports_dir))

    secret = tmp_path / "secret.html"
    secret.write_text("<html>secret</html>", encoding="utf-8")

    with pytest.raises(ReportPathError):
        report_reader.read_strategy_report(str(secret))


def test_absolute_system_path_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    # Even a real, readable system file must not be accessible.
    with pytest.raises(ReportPathError):
        report_reader.read_strategy_report("/etc/hostname")


def test_parent_traversal_is_rejected(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(reports_dir))

    secret = tmp_path / "secret.html"
    secret.write_text("<html>secret</html>", encoding="utf-8")

    with pytest.raises(ReportPathError):
        report_reader.read_strategy_report("../secret.html")


def test_non_html_extension_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    (tmp_path / "passwd.txt").write_text("not a report", encoding="utf-8")

    with pytest.raises(ReportPathError):
        report_reader.read_strategy_report("passwd.txt")


def test_non_html_extension_message_mentions_base_dir_and_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    with pytest.raises(ReportPathError) as exc_info:
        report_reader.read_strategy_report("passwd.txt")
    msg = str(exc_info.value)
    assert str(tmp_path) in msg
    assert "MT5_MCP_REPORTS_DIR" in msg


def test_default_reports_dir_used_when_env_unset(tmp_path, monkeypatch):
    # With MT5_MCP_REPORTS_DIR unset, paths resolve under <cwd>/reports.
    monkeypatch.delenv("MT5_MCP_REPORTS_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    default_dir = tmp_path / "reports"
    default_dir.mkdir()
    (default_dir / "report.html").write_text(SAMPLE_REPORT_HTML, encoding="utf-8")

    result = report_reader.read_strategy_report("report.html")
    assert result["summary"]["Total Trades"] == "500"


def test_symlink_escaping_reports_dir_is_rejected(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(reports_dir))

    secret = tmp_path / "secret.html"
    secret.write_text("<html>secret</html>", encoding="utf-8")

    link = reports_dir / "escape.html"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform/filesystem")

    with pytest.raises(ReportPathError):
        report_reader.read_strategy_report("escape.html")
