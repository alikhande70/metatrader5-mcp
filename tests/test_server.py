from __future__ import annotations

from mt5_mcp.permissions import ActionCategory, classify
from mt5_mcp.server import mcp

EXPECTED_SAFE_READ = {
    "get_account_info", "get_terminal_info", "get_symbol_info", "get_tick", "get_rates",
    "get_positions", "get_orders", "get_history_deals", "read_log", "read_strategy_report",
}
EXPECTED_SAFE_ANALYSIS = {
    "summarize_positions", "analyze_drawdown", "analyze_trade_history", "calculate_profit_risk_basic",
}
EXPECTED_REQUIRES_APPROVAL = {"calculate_margin", "calculate_profit", "check_order", "prepare_order_plan"}


def _registered_tool_names() -> set[str]:
    return {tool.name for tool in mcp._tool_manager.list_tools()}


def test_all_expected_tools_are_registered():
    names = _registered_tool_names()
    assert names == EXPECTED_SAFE_READ | EXPECTED_SAFE_ANALYSIS | EXPECTED_REQUIRES_APPROVAL


def test_every_registered_tool_has_a_non_blocked_classification():
    for name in _registered_tool_names():
        category = classify(name)
        assert category is not ActionCategory.BLOCKED, f"registered tool '{name}' must not classify as BLOCKED"


def test_order_planning_tools_require_approval():
    for name in EXPECTED_REQUIRES_APPROVAL:
        assert classify(name) is ActionCategory.REQUIRES_APPROVAL


def test_no_send_order_tool_is_registered():
    blocked_names = {"send_order", "place_order", "modify_order", "cancel_order", "close_position", "execute_trade"}
    assert _registered_tool_names().isdisjoint(blocked_names)
