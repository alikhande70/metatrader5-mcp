"""Order planning tools: calculate_margin, calculate_profit, check_order, prepare_order_plan.

PHASE 1 RULE: nothing in this module calls order_send. These functions only
calculate numbers and run MT5's own dry-run validation (order_check). Every
function here re-fetches account_info and calls risk_guard.guard_order_tool()
first, so they only ever run against a demo account with demo trading
explicitly enabled (MT5_MCP_ENABLE_DEMO_TRADING=true). Real/contest accounts
are always blocked, with no override.
"""

from __future__ import annotations

from typing import Any

from . import mt5_bridge
from .risk_guard import guard_order_tool
from .utils import new_id, utcnow_iso


def _guarded(action_name: str) -> dict:
    """Fetch fresh account info and enforce the risk guard before any order-planning call."""
    account_info = mt5_bridge.get_account_info()
    guard_order_tool(account_info, action_name)
    return account_info


def calculate_margin(order_type: str, symbol: str, volume: float, price: float) -> dict:
    _guarded("calculate_margin")
    margin = mt5_bridge.calc_margin(order_type, symbol, volume, price)
    return {
        "order_type": order_type,
        "symbol": symbol,
        "volume": volume,
        "price": price,
        "required_margin": margin,
    }


def calculate_profit(order_type: str, symbol: str, volume: float, price_open: float, price_close: float) -> dict:
    _guarded("calculate_profit")
    profit = mt5_bridge.calc_profit(order_type, symbol, volume, price_open, price_close)
    return {
        "order_type": order_type,
        "symbol": symbol,
        "volume": volume,
        "price_open": price_open,
        "price_close": price_close,
        "estimated_profit": profit,
    }


def build_order_request(
    order_type: str,
    symbol: str,
    volume: float,
    price: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 20,
    magic: int = 0,
    comment: str = "mt5-mcp plan (not sent)",
) -> dict[str, Any]:
    mt5 = mt5_bridge.mt5_module()
    type_const = mt5_bridge.resolve_order_type(order_type)
    is_pending = order_type.strip().upper() not in {"BUY", "SELL"}

    request: dict[str, Any] = {
        "action": mt5.TRADE_ACTION_PENDING if is_pending else mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": type_const,
        "price": price,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    if sl is not None:
        request["sl"] = sl
    if tp is not None:
        request["tp"] = tp
    return request


def check_order(
    order_type: str,
    symbol: str,
    volume: float,
    price: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 20,
    magic: int = 0,
    comment: str = "mt5-mcp check (not sent)",
) -> dict:
    """Build a request and run MT5's server-side order_check validation. Never sends the order."""
    _guarded("check_order")
    request = build_order_request(order_type, symbol, volume, price, sl, tp, deviation, magic, comment)
    result = mt5_bridge.order_check(request)
    return {"request": request, "check_result": result, "sent": False}


def prepare_order_plan(
    order_type: str,
    symbol: str,
    volume: float,
    price: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 20,
    magic: int = 0,
    comment: str = "mt5-mcp plan (not sent)",
) -> dict:
    """Assemble a full order plan: request + margin + estimated profit/loss + order_check.

    This NEVER sends an order. The plan's status is always "PLANNED_NOT_SENT" -
    sending orders is not implemented in Phase 1.
    """
    account_info = _guarded("prepare_order_plan")

    request = build_order_request(order_type, symbol, volume, price, sl, tp, deviation, magic, comment)
    margin = mt5_bridge.calc_margin(order_type, symbol, volume, price)

    estimated_profit_at_tp = mt5_bridge.calc_profit(order_type, symbol, volume, price, tp) if tp is not None else None
    estimated_loss_at_sl = mt5_bridge.calc_profit(order_type, symbol, volume, price, sl) if sl is not None else None
    check_result = mt5_bridge.order_check(request)

    return {
        "plan_id": new_id("plan"),
        "created_at": utcnow_iso(),
        "status": "PLANNED_NOT_SENT",
        "account_trade_mode": account_info.get("trade_mode"),
        "request": request,
        "required_margin": margin,
        "estimated_profit_at_tp": estimated_profit_at_tp,
        "estimated_loss_at_sl": estimated_loss_at_sl,
        "order_check_result": check_result,
        "note": "This plan was NOT sent to the broker. Order execution is not implemented in Phase 1.",
    }
