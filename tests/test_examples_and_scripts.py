"""Tests for the Phase 2 examples, client config, docs, and readiness helper.

These guard the safety posture of the user-facing extras: the readiness script
must stay a plain read-only helper (never an MCP tool, never an order sender),
the example client must not contain execution calls, the example configs must be
valid JSON, and the docs must keep saying planning is not execution.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "mt5_readiness_check.py"
CLIENT_PATH = REPO_ROOT / "examples" / "example_client.py"
DESKTOP_CONFIG = REPO_ROOT / "examples" / "claude_desktop_config.example.json"
CODE_CONFIG = REPO_ROOT / "examples" / "claude_code_config.example.json"
EXAMPLES_DOC = REPO_ROOT / "docs" / "EXAMPLES.md"
TROUBLESHOOTING_DOC = REPO_ROOT / "docs" / "TROUBLESHOOTING.md"

# Tokens that would indicate order execution anywhere it must not appear.
_EXECUTION_TOKENS = (
    "order_send",
    "send_order",
    "place_order",
    "modify_order",
    "cancel_order",
    "delete_order",
    "close_position",
    "close_order",
)


def _load_readiness_module():
    import sys

    spec = importlib.util.spec_from_file_location("mt5_readiness_check", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Register before exec so @dataclass introspection can resolve the module.
    sys.modules["mt5_readiness_check"] = module
    spec.loader.exec_module(module)
    return module


# --- readiness script: not an MCP tool, read-only ---------------------------


def test_readiness_script_exists():
    assert SCRIPT_PATH.is_file()


def test_readiness_script_is_not_an_mcp_tool():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "@mcp.tool" not in source
    assert "mcp.tool" not in source
    assert "FastMCP" not in source


def test_readiness_script_has_no_execution_calls():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for token in _EXECUTION_TOKENS:
        assert token not in source, f"readiness script must not reference {token!r}"
    # It must also not invoke the REQUIRES_APPROVAL planning tools.
    for token in ("calculate_margin", "calculate_profit", "check_order", "prepare_order_plan", "order_tools"):
        assert token not in source, f"readiness script must not call planning tool {token!r}"


def test_readiness_checks_pass_with_fake_mt5(fake_mt5):
    module = _load_readiness_module()
    fake_mt5.rates["EURUSD"] = [
        {"time": 1700000000, "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "tick_volume": 100},
    ]
    results = module.run_checks(symbol="EURUSD")
    statuses = {r.name: r.status for r in results}
    # No hard failures against a healthy fake terminal.
    assert module.exit_code(results) == 0
    assert all(r.status != module.FAIL for r in results)
    assert statuses["MetaTrader5 package available"] == module.PASS
    assert statuses["Account info"] == module.PASS


def test_readiness_reports_failure_when_mt5_unavailable(monkeypatch):
    module = _load_readiness_module()
    from mt5_mcp import mt5_bridge

    def _raise():
        raise mt5_bridge.MT5NotAvailableError("not available")

    monkeypatch.setattr(mt5_bridge, "mt5_module", _raise)
    results = module.run_checks(symbol="EURUSD")
    assert module.exit_code(results) == 1
    availability = next(r for r in results if r.name == "MetaTrader5 package available")
    assert availability.status == module.FAIL


def test_readiness_does_not_call_order_functions(fake_mt5):
    # The FakeMT5 has no order_send/order placement attributes; even calc helpers
    # should not be touched. We assert the fake never gained an order_send and that
    # running the checks does not raise.
    module = _load_readiness_module()
    results = module.run_checks(symbol="EURUSD")
    assert not hasattr(fake_mt5, "order_send")
    assert isinstance(results, list) and results


def test_readiness_table_mentions_read_only():
    module = _load_readiness_module()
    text = module.format_table([module.CheckResult("x", module.PASS, "y")])
    assert "read-only" in text.lower()


# --- example client: no execution calls -------------------------------------


def test_example_client_has_no_execution_calls():
    source = CLIENT_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()
    for token in _EXECUTION_TOKENS:
        offending = [ln for ln in lines if token in ln and not ln.lstrip().startswith("#")]
        # order_send is allowed only in comments/docstrings stating it is absent.
        assert not any(f"{token}(" in ln for ln in offending), f"client must not call {token}"


def test_example_client_demonstrates_three_tiers():
    source = CLIENT_PATH.read_text(encoding="utf-8")
    assert "get_account_info" in source  # SAFE_READ
    assert "calculate_profit_risk_basic" in source  # SAFE_ANALYSIS
    assert "prepare_order_plan" in source  # REQUIRES_APPROVAL planning


def test_example_client_states_not_sent():
    source = CLIENT_PATH.read_text(encoding="utf-8")
    assert "not sent" in source.lower() or "not execution" in source.lower()


# --- example configs: valid JSON --------------------------------------------


@pytest.mark.parametrize("config_path", [DESKTOP_CONFIG, CODE_CONFIG])
def test_example_config_is_valid_json(config_path):
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "mcpServers" in data
    server = data["mcpServers"]["metatrader5"]
    assert server["args"] == ["-m", "mt5_mcp.server"]
    # Demo trading must default to disabled in the shipped examples.
    assert server["env"]["MT5_MCP_ENABLE_DEMO_TRADING"] == "false"


# --- docs: planning is not execution ----------------------------------------


def test_examples_doc_states_planning_is_not_execution():
    text = EXAMPLES_DOC.read_text(encoding="utf-8").lower()
    assert "planning is not execution" in text
    assert "no order is" in text and "sent" in text


def test_troubleshooting_doc_covers_key_failure_modes():
    text = TROUBLESHOOTING_DOC.read_text(encoding="utf-8").lower()
    for phrase in (
        "venv",
        "metatrader5 package missing",
        "non-windows",
        "terminal not running",
        "mt5_path",
        "not logged in",
        "symbol not found",
        "report not found",
        "log not found",
        "approval timeout",
        "risk_guard",
        "stdio",
    ):
        assert phrase in text, f"TROUBLESHOOTING.md should cover {phrase!r}"
