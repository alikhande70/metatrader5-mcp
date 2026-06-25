"""Risk guard: live trading is always blocked; demo trading utilities are opt-in (default OFF).

Order-planning tools (calculate_margin, calculate_profit, check_order,
prepare_order_plan) call `guard_order_tool()` before doing anything else.
There is no override for a real/contest account - only a demo account with
MT5_MCP_ENABLE_DEMO_TRADING=true is allowed through.
"""

from __future__ import annotations

import os

from .utils import get_logger

logger = get_logger(__name__)

ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_TRADE_MODE_CONTEST = 1
ACCOUNT_TRADE_MODE_REAL = 2

_TRADE_MODE_NAMES = {
    ACCOUNT_TRADE_MODE_DEMO: "demo",
    ACCOUNT_TRADE_MODE_CONTEST: "contest",
    ACCOUNT_TRADE_MODE_REAL: "real",
}


class RiskGuardError(PermissionError):
    """Raised when a trading-adjacent action is blocked by the risk guard."""


def is_demo_trading_enabled() -> bool:
    return os.environ.get("MT5_MCP_ENABLE_DEMO_TRADING", "false").strip().lower() in {"1", "true", "yes"}


def is_live_account(account_info: dict) -> bool:
    return account_info.get("trade_mode") != ACCOUNT_TRADE_MODE_DEMO


def guard_order_tool(account_info: dict, action_name: str) -> None:
    """Raise RiskGuardError unless the account is demo AND demo trading is explicitly enabled."""
    trade_mode = account_info.get("trade_mode")
    mode_name = _TRADE_MODE_NAMES.get(trade_mode, f"unknown({trade_mode})")

    if trade_mode != ACCOUNT_TRADE_MODE_DEMO:
        logger.warning("Risk guard blocked '%s' on a %s account; live trading is never allowed.", action_name, mode_name)
        raise RiskGuardError(
            f"'{action_name}' is blocked: the connected account is '{mode_name}', not demo. "
            "Live trading is never allowed in Phase 1."
        )

    if not is_demo_trading_enabled():
        logger.warning("Risk guard blocked '%s' on a demo account because demo trading is disabled.", action_name)
        raise RiskGuardError(
            f"'{action_name}' is blocked: demo trading utilities are disabled by default. "
            "Set MT5_MCP_ENABLE_DEMO_TRADING=true to enable them on a demo account."
        )
