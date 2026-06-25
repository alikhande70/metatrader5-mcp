"""Action classification: every tool name maps to exactly one permission category.

Unknown action names are treated as BLOCKED (fail closed), never as SAFE.
"""

from __future__ import annotations

from enum import Enum


class ActionCategory(str, Enum):
    SAFE_READ = "SAFE_READ"
    SAFE_ANALYSIS = "SAFE_ANALYSIS"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    BLOCKED = "BLOCKED"


SAFE_READ: frozenset[str] = frozenset(
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

SAFE_ANALYSIS: frozenset[str] = frozenset(
    {
        "summarize_positions",
        "analyze_drawdown",
        "analyze_trade_history",
        "calculate_profit_risk_basic",
    }
)

# Order-planning tools. They never call order_send, but they are the closest
# thing to "real trading" in Phase 1 (they touch margin/risk numbers and build
# an order request), so a human must approve each call.
REQUIRES_APPROVAL: frozenset[str] = frozenset(
    {
        "calculate_margin",
        "calculate_profit",
        "check_order",
        "prepare_order_plan",
    }
)

# No Phase 1 tool implements any of these - this list is a defense-in-depth
# safety net so the router refuses them by name on sight, even if a future
# change accidentally wires one up.
BLOCKED: frozenset[str] = frozenset(
    {
        "send_order",
        "place_order",
        "modify_order",
        "cancel_order",
        "delete_order",
        "close_position",
        "close_order",
        "execute_trade",
        "live_trade",
    }
)

_CATEGORY_BY_ACTION: dict[str, ActionCategory] = {
    **{name: ActionCategory.SAFE_READ for name in SAFE_READ},
    **{name: ActionCategory.SAFE_ANALYSIS for name in SAFE_ANALYSIS},
    **{name: ActionCategory.REQUIRES_APPROVAL for name in REQUIRES_APPROVAL},
    **{name: ActionCategory.BLOCKED for name in BLOCKED},
}


def classify(action_name: str) -> ActionCategory:
    """Classify an action name, defaulting unknown actions to BLOCKED."""
    return _CATEGORY_BY_ACTION.get(action_name, ActionCategory.BLOCKED)
