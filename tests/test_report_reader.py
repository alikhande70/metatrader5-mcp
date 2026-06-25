from __future__ import annotations

import pytest

from mt5_mcp import report_reader

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


def test_read_strategy_report_parses_summary(tmp_path):
    report_path = tmp_path / "ReportTester.html"
    report_path.write_text(SAMPLE_REPORT_HTML, encoding="utf-8")

    result = report_reader.read_strategy_report(str(report_path))

    assert result["summary"]["Total Net Profit"] == "2099.42"
    assert result["summary"]["Profit Factor"] == "1.57"
    assert result["summary"]["Total Trades"] == "500"
    assert len(result["raw_rows"]) >= 3


def test_read_strategy_report_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        report_reader.read_strategy_report(str(tmp_path / "missing.html"))


def test_read_strategy_report_resolves_relative_to_reports_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(tmp_path))
    (tmp_path / "report.html").write_text(SAMPLE_REPORT_HTML, encoding="utf-8")

    result = report_reader.read_strategy_report("report.html")
    assert result["summary"]["Total Trades"] == "500"
