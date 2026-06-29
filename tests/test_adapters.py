from __future__ import annotations

import sys

import pytest

from mt5_mcp import code_gen, metaeditor_adapter, tester_adapter, workspace_tools


# --- workspace ---------------------------------------------------------------


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "ws"
    (root / "Experts").mkdir(parents=True)
    (root / "Include").mkdir(parents=True)
    (root / "Experts" / "A.mq5").write_text("void OnTick(){}\n", encoding="utf-8")
    (root / "Include" / "lib.mqh").write_text("#define X 1\n", encoding="utf-8")
    monkeypatch.setenv("MT5_MCP_WORKSPACE_DIR", str(root))
    monkeypatch.setenv("MT5_MCP_BACKUPS_DIR", str(tmp_path / "backups"))
    return root


def test_workspace_status_and_listing(workspace):
    status = workspace_tools.show_status()
    assert status["exists"]
    assert status["counts"]["experts"] == 1
    experts = workspace_tools.list_sources("experts")["files"]
    assert any("A.mq5" in f for f in experts)
    includes = workspace_tools.list_sources("includes")["files"]
    assert any("lib.mqh" in f for f in includes)


def test_workspace_snapshot_and_restore(workspace):
    snap = workspace_tools.snapshot("test")
    assert snap["file_count"] >= 2
    (workspace / "Experts" / "A.mq5").write_text("changed\n", encoding="utf-8")
    from pathlib import Path

    workspace_tools.restore_snapshot(Path(snap["archive"]).name)
    assert (workspace / "Experts" / "A.mq5").read_text() == "void OnTick(){}\n"


def test_list_unknown_kind_raises(workspace):
    with pytest.raises(ValueError):
        workspace_tools.list_sources("nope")


# --- metaeditor adapter ------------------------------------------------------

_LOG = """MyEA.mq5(34,10) : error 245: 'x' - undeclared identifier
MyEA.mq5(50,3) : warning 43: possible loss of data due to type conversion
Result: 1 errors, 1 warnings
"""


def test_parse_errors_and_warnings():
    errors = metaeditor_adapter.parse_errors(_LOG)
    warnings = metaeditor_adapter.parse_warnings(_LOG)
    assert errors["count"] == 1
    assert errors["errors"][0]["line"] == 34
    assert errors["errors"][0]["code"] == 245
    assert warnings["count"] == 1
    assert warnings["warnings"][0]["line"] == 50


def test_prepare_compile_builds_command():
    out = metaeditor_adapter.prepare_compile("Experts/A.mq5")
    assert any("/compile:" in part for part in out["command"])
    assert out["expected_log"].endswith(".log")


def test_run_compile_is_gated_off_windows():
    if sys.platform == "win32":
        pytest.skip("Windows path tested separately")
    out = metaeditor_adapter.run_compile("Experts/A.mq5")
    assert out["status"] == metaeditor_adapter.UNSUPPORTED
    assert out["reason"] == metaeditor_adapter.REQUIRES_WINDOWS


def test_generate_fix_plan_from_log():
    plan = metaeditor_adapter.generate_fix_plan(_LOG, source_path="Experts/A.mq5")
    assert plan["error_count"] == 1
    assert "undeclared" in plan["fix_plan"][0]["suggested_fix"].lower() or plan["fix_plan"][0]["suggested_fix"]


# --- tester adapter ----------------------------------------------------------


def test_prepare_signal_only_test_builds_ini():
    out = tester_adapter.prepare_signal_only_test("A.ex5", "EURUSD")
    assert "[Tester]" in out["ini"]
    assert "Expert=A.ex5" in out["ini"]


def test_run_backtest_is_gated_off_windows():
    if sys.platform == "win32":
        pytest.skip("Windows path tested separately")
    out = tester_adapter.run_backtest_if_supported()
    assert out["status"] == tester_adapter.UNSUPPORTED


def test_import_csv(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "trades.csv").write_text("ticket;profit\n1;10.5\n2;-3.0\n", encoding="utf-8")
    monkeypatch.setenv("MT5_MCP_REPORTS_DIR", str(reports))
    out = tester_adapter.import_csv("trades.csv")
    assert out["row_count"] == 2
    assert out["header"] == ["ticket", "profit"]
    assert out["rows"][0]["profit"] == "10.5"


def test_review_and_compare_runs():
    summary_a = {"Profit factor": "1.8", "Total net profit": "1200", "Maximal drawdown": "150", "Total trades": "120"}
    summary_b = {"Profit factor": "0.9", "Total net profit": "-100", "Maximal drawdown": "300", "Total trades": "20"}
    review_a = tester_adapter.review_results(summary_a)
    review_b = tester_adapter.review_results(summary_b)
    assert review_a["metrics"]["profit_factor"] == 1.8
    assert any("below 1.0" in f for f in review_b["flags"])
    cmp = tester_adapter.compare_runs([{"label": "A", **summary_a}, {"label": "B", **summary_b}])
    assert cmp["best_profit_factor"] == "A"


def test_generate_backtest_report_markdown():
    review = tester_adapter.review_results({"Profit factor": "1.5", "Total trades": "50"})
    out = tester_adapter.generate_backtest_report(review, title="My Run")
    assert out["markdown"].startswith("# My Run")


# --- code_gen ----------------------------------------------------------------


def test_generate_ea_returns_code():
    out = code_gen.generate_ea("MyEA", magic=12345)
    assert "OnTick" in out["code"]
    assert "12345" in out["code"]
    assert out["suggested_path"] == "Experts/MyEA.mq5"


def test_code_review_flags_execution(tmp_path, monkeypatch):
    root = tmp_path / "ws"
    (root / "Experts").mkdir(parents=True)
    (root / "Experts" / "Trade.mq5").write_text("void OnTick(){ CTrade t; t.Buy(0.1); }\n", encoding="utf-8")
    monkeypatch.setenv("MT5_MCP_WORKSPACE_DIR", str(root))
    out = code_gen.code_review("Experts/Trade.mq5")
    assert out["flags"]["uses_OrderSend"]
    assert any("magic" in f.lower() or "stop-loss" in f.lower() for f in out["findings"])
