from __future__ import annotations

from mt5_mcp.permissions import ActionCategory, classify


def test_safe_read_actions_classified():
    for name in ["get_account_info", "get_terminal_info", "get_symbol_info", "get_tick", "get_rates",
                 "get_positions", "get_orders", "get_history_deals", "read_log", "read_strategy_report"]:
        assert classify(name) is ActionCategory.SAFE_READ


def test_safe_analysis_actions_classified():
    for name in ["summarize_positions", "analyze_drawdown", "analyze_trade_history", "calculate_profit_risk_basic"]:
        assert classify(name) is ActionCategory.SAFE_ANALYSIS


def test_requires_approval_actions_classified():
    for name in ["calculate_margin", "calculate_profit", "check_order", "prepare_order_plan"]:
        assert classify(name) is ActionCategory.REQUIRES_APPROVAL


def test_blocked_actions_classified():
    for name in ["send_order", "place_order", "modify_order", "cancel_order", "close_position"]:
        assert classify(name) is ActionCategory.BLOCKED


def test_unknown_action_defaults_to_blocked():
    assert classify("totally_made_up_action") is ActionCategory.BLOCKED
