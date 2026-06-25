"""Regression-lock tests for the safety invariants that must never silently change.

These complement the more detailed tests in test_permissions.py, test_server.py,
test_action_router.py, and test_risk_guard.py by asserting the exact, hardcoded
shape of the safety surface in one place, so any accidental change to tool count,
category membership, or blocked-name coverage fails loudly here.
"""

from __future__ import annotations

from pathlib import Path

from mt5_mcp.permissions import BLOCKED, REQUIRES_APPROVAL, SAFE_ANALYSIS, SAFE_READ, ActionCategory, classify
from mt5_mcp.server import mcp

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

EXPECTED_TOOL_COUNT = 18

EXPECTED_SAFE_READ = frozenset(
    {
        "get_account_info",
        "get_terminal_info",
        "get_symbol_info",
        "get_tick",
        "get_rates",
        "get_positions",
        "get_orders",
        "get_history_deals",
        "read_log",
        "read_strategy_report",
    }
)
EXPECTED_SAFE_ANALYSIS = frozenset(
    {
        "summarize_positions",
        "analyze_drawdown",
        "analyze_trade_history",
        "calculate_profit_risk_basic",
    }
)
EXPECTED_REQUIRES_APPROVAL = frozenset(
    {
        "calculate_margin",
        "calculate_profit",
        "check_order",
        "prepare_order_plan",
    }
)

_EXECUTION_NAMED_TOOLS = (
    "send_order",
    "place_order",
    "modify_order",
    "cancel_order",
    "delete_order",
    "close_position",
    "close_order",
    "execute_trade",
    "live_trade",
)


def _registered_tool_names() -> set[str]:
    return {tool.name for tool in mcp._tool_manager.list_tools()}


def test_mcp_tool_count_is_exactly_18():
    assert len(_registered_tool_names()) == EXPECTED_TOOL_COUNT


def test_safe_read_set_is_unchanged():
    assert SAFE_READ == EXPECTED_SAFE_READ


def test_safe_analysis_set_is_unchanged():
    assert SAFE_ANALYSIS == EXPECTED_SAFE_ANALYSIS


def test_requires_approval_set_is_unchanged():
    assert REQUIRES_APPROVAL == EXPECTED_REQUIRES_APPROVAL


def test_no_execution_named_tool_is_registered():
    names = _registered_tool_names()
    for token in _EXECUTION_NAMED_TOOLS:
        assert token not in names


def test_execution_named_actions_classify_as_blocked():
    for token in _EXECUTION_NAMED_TOOLS:
        assert classify(token) is ActionCategory.BLOCKED
        assert token in BLOCKED


def test_unknown_action_is_blocked_fail_closed():
    for name in ("totally_unknown_action", "", "GET_ACCOUNT_INFO", "get_account_info "):
        assert classify(name) is ActionCategory.BLOCKED


def test_no_order_send_call_exists_in_src():
    offenders = []
    for path in SRC_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "order_send(" in line:
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, f"order_send(...) call found in src/: {offenders}"


def test_no_execution_function_defined_in_src():
    forbidden_defs = tuple(
        f"def {name}"
        for name in (
            "order_send",
            "send_order",
            "place_order",
            "modify_order",
            "cancel_order",
            "delete_order",
            "close_position",
            "close_order",
        )
    )
    offenders = []
    for path in SRC_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in forbidden_defs:
            if forbidden in text:
                offenders.append(f"{path}: {forbidden}")
    assert not offenders, f"forbidden function definition found in src/: {offenders}"
