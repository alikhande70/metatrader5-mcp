"""mt5_mcp FastMCP server: registers all Phase 1 tools.

Every tool body below is a thin call into mt5_bridge / analysis_tools /
order_tools / log_reader / report_reader, routed through
action_router.dispatch() so permission classification, approval gating, and
action logging can never be skipped. No tool here sends, modifies, or
cancels an order - Phase 1 is read + analysis + planning only.
"""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from . import analysis_tools, log_reader, mt5_bridge, order_tools, report_reader
from .action_router import dispatch
from .approval_gate import get_approval_gate
from .utils import get_logger

logger = get_logger(__name__)

mcp = FastMCP(
    "metatrader5-mcp",
    instructions=(
        "Phase 1 MCP server for MetaTrader 5: read-only market/account data, "
        "trading-performance analysis, and order PLANNING only. No tool in this "
        "server sends, modifies, or cancels a real order, and live trading is "
        "always blocked regardless of approval."
    ),
)

_approval_gate = get_approval_gate()


def _run(action_name: str, fn: Callable[..., Any], params: dict[str, Any], description: str | None = None) -> Any:
    return dispatch(action_name, lambda: fn(**params), params, approval_gate=_approval_gate, description=description)


# --- SAFE_READ ---------------------------------------------------------------


@mcp.tool()
def get_account_info() -> dict:
    """Get the connected MT5 account's balance, equity, margin, leverage, and trade mode."""
    return _run("get_account_info", mt5_bridge.get_account_info, {})


@mcp.tool()
def get_terminal_info() -> dict:
    """Get MT5 terminal status: connection state, data path, build, trade-allowed flags."""
    return _run("get_terminal_info", mt5_bridge.get_terminal_info, {})


@mcp.tool()
def get_symbol_info(symbol: str) -> dict:
    """Get full symbol specification (point, digits, contract size, spread, limits) for `symbol`."""
    return _run("get_symbol_info", mt5_bridge.get_symbol_info, {"symbol": symbol})


@mcp.tool()
def get_tick(symbol: str) -> dict:
    """Get the latest bid/ask/last tick for `symbol`."""
    return _run("get_tick", mt5_bridge.get_tick, {"symbol": symbol})


@mcp.tool()
def get_rates(symbol: str, timeframe: str, count: int = 100, start_pos: int = 0) -> list[dict]:
    """Get OHLCV bars for `symbol` on `timeframe` (e.g. M1, M15, H1, H4, D1)."""
    return _run(
        "get_rates",
        mt5_bridge.get_rates,
        {"symbol": symbol, "timeframe": timeframe, "count": count, "start_pos": start_pos},
    )


@mcp.tool()
def get_positions(symbol: str | None = None, ticket: int | None = None) -> list[dict]:
    """List open positions, optionally filtered by symbol or ticket."""
    return _run("get_positions", mt5_bridge.get_positions, {"symbol": symbol, "ticket": ticket})


@mcp.tool()
def get_orders(symbol: str | None = None, ticket: int | None = None) -> list[dict]:
    """List active pending orders, optionally filtered by symbol or ticket."""
    return _run("get_orders", mt5_bridge.get_orders, {"symbol": symbol, "ticket": ticket})


@mcp.tool()
def get_history_deals(
    date_from: str | None = None,
    date_to: str | None = None,
    ticket: int | None = None,
    position: int | None = None,
    group: str | None = None,
) -> list[dict]:
    """List historical deals between date_from/date_to (ISO dates), or by ticket/position."""
    return _run(
        "get_history_deals",
        mt5_bridge.get_history_deals,
        {"date_from": date_from, "date_to": date_to, "ticket": ticket, "position": position, "group": group},
    )


@mcp.tool()
def read_log(date: str | None = None, lines: int = 200, kind: str = "terminal") -> dict:
    """Read the tail of an MT5 log file for `date` (YYYYMMDD, default today). kind: 'terminal' or 'experts'."""
    return _run("read_log", log_reader.read_log, {"date": date, "lines": lines, "kind": kind})


@mcp.tool()
def read_strategy_report(path: str) -> dict:
    """Parse an MT5 Strategy Tester HTML report into a summary dict and raw table rows."""
    return _run("read_strategy_report", report_reader.read_strategy_report, {"path": path})


# --- SAFE_ANALYSIS ------------------------------------------------------------


@mcp.tool()
def summarize_positions(positions: list[dict] | None = None) -> dict:
    """Summarize open positions by total, symbol, and side. Fetches live positions if `positions` is omitted."""
    data = positions if positions is not None else mt5_bridge.get_positions()
    return _run("summarize_positions", analysis_tools.summarize_positions, {"positions": data})


@mcp.tool()
def analyze_drawdown(
    deals: list[dict] | None = None,
    starting_balance: float = 0.0,
    include_curve: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Compute basic peak-to-trough drawdown from history deals (fetched live if `deals` is omitted)."""
    data = deals if deals is not None else mt5_bridge.get_history_deals(date_from, date_to)
    return _run(
        "analyze_drawdown",
        analysis_tools.analyze_drawdown,
        {"deals": data, "starting_balance": starting_balance, "include_curve": include_curve},
    )


@mcp.tool()
def analyze_trade_history(
    deals: list[dict] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Compute win rate / profit factor / averages from history deals (fetched live if `deals` is omitted)."""
    data = deals if deals is not None else mt5_bridge.get_history_deals(date_from, date_to)
    return _run("analyze_trade_history", analysis_tools.analyze_trade_history, {"deals": data})


@mcp.tool()
def calculate_profit_risk_basic(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    volume: float = 1.0,
    value_per_point: float | None = None,
) -> dict:
    """Pure price-math risk/reward ratio calculation. No MT5 connection or symbol lookup needed."""
    return _run(
        "calculate_profit_risk_basic",
        analysis_tools.calculate_profit_risk_basic,
        {
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "volume": volume,
            "value_per_point": value_per_point,
        },
    )


# --- ORDER PLANNING (REQUIRES_APPROVAL; demo accounts only; never sends) ----


@mcp.tool()
def calculate_margin(order_type: str, symbol: str, volume: float, price: float) -> dict:
    """Calculate required margin for a hypothetical order. Requires approval; demo accounts only; never sent."""
    return _run(
        "calculate_margin",
        order_tools.calculate_margin,
        {"order_type": order_type, "symbol": symbol, "volume": volume, "price": price},
        description=f"Calculate margin for {order_type} {volume} {symbol} @ {price}",
    )


@mcp.tool()
def calculate_profit(order_type: str, symbol: str, volume: float, price_open: float, price_close: float) -> dict:
    """Calculate hypothetical profit/loss between two prices. Requires approval; demo accounts only; never sent."""
    return _run(
        "calculate_profit",
        order_tools.calculate_profit,
        {
            "order_type": order_type,
            "symbol": symbol,
            "volume": volume,
            "price_open": price_open,
            "price_close": price_close,
        },
        description=f"Calculate profit for {order_type} {volume} {symbol} {price_open} -> {price_close}",
    )


@mcp.tool()
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
    """Run MT5's server-side order_check validation for a hypothetical order. Requires approval; demo only; never sent."""
    return _run(
        "check_order",
        order_tools.check_order,
        {
            "order_type": order_type,
            "symbol": symbol,
            "volume": volume,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": deviation,
            "magic": magic,
            "comment": comment,
        },
        description=f"Check order {order_type} {volume} {symbol} @ {price} (sl={sl}, tp={tp})",
    )


@mcp.tool()
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
    """Build a full order plan (request + margin + estimated P/L + order_check). Requires approval; demo only; NEVER sent."""
    return _run(
        "prepare_order_plan",
        order_tools.prepare_order_plan,
        {
            "order_type": order_type,
            "symbol": symbol,
            "volume": volume,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": deviation,
            "magic": magic,
            "comment": comment,
        },
        description=f"Prepare order plan {order_type} {volume} {symbol} @ {price} (sl={sl}, tp={tp})",
    )


def main() -> None:
    logger.info("Starting metatrader5-mcp server (Phase 1: read + analysis + planning only, no execution).")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
