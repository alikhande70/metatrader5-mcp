"""Thin wrapper around the MetaTrader5 Python package.

This module is the only place that talks to the `MetaTrader5` package directly.
Everything else in mt5_mcp goes through the functions below so that:
  - the MetaTrader5 import stays lazy (it only works on Windows, next to a
    running MT5 terminal, so importing it eagerly would break this package
    on every other platform), and
  - tests can inject a fake module via `_mt5_module` without a real terminal.

No function in this file sends, modifies, or cancels an order. Phase 1 is
read + planning only; `order_send` is intentionally never called here.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any

from .utils import get_logger, mt5_struct_to_dict

logger = get_logger(__name__)

_mt5_module: Any = None
_connected = False


class MT5NotAvailableError(RuntimeError):
    """Raised when the MetaTrader5 package cannot be imported on this platform."""


class MT5ConnectionError(RuntimeError):
    """Raised when initialize()/login() to the MT5 terminal fails."""


class MT5RequestError(RuntimeError):
    """Raised when an MT5 API call returns None (the package's error signal)."""


def _mt5_unavailable_message() -> str:
    """Build the MT5NotAvailableError message, tailored to why the import failed."""
    if sys.platform != "win32":
        return (
            f"The MetaTrader5 package is not available on this platform ('{sys.platform}'). "
            "It only works on Windows, running next to a live MetaTrader 5 terminal. This server "
            "still starts and lists its tools on other platforms, but every tool that touches MT5 "
            "will raise this error until it is run on Windows next to the terminal."
        )
    return (
        "The MetaTrader5 package is not installed in this Python environment, even though this "
        "is Windows. Install it with `pip install MetaTrader5` (or `pip install -e \".[dev]\"` from "
        "the project root, which pulls it in automatically on win32), then restart the server."
    )


def _get_mt5() -> Any:
    global _mt5_module
    if _mt5_module is not None:
        return _mt5_module
    try:
        import MetaTrader5 as mt5  # type: ignore[import-not-found]
    except ImportError as exc:
        raise MT5NotAvailableError(_mt5_unavailable_message()) from exc
    _mt5_module = mt5
    return mt5


def mt5_module() -> Any:
    """Expose the underlying MetaTrader5 module for callers that need its raw constants."""
    return _get_mt5()


def _raise_last_error(mt5: Any, action: str, *, symbol: str | None = None) -> None:
    code, desc = mt5.last_error()
    message = f"{action} failed: ({code}) {desc}"
    if symbol:
        message += (
            f" symbol_select('{symbol}', True) was attempted first to make it visible in Market "
            f"Watch; '{symbol}' may not exist on this broker/server, or may need to be added to "
            "Market Watch manually in the terminal."
        )
    raise MT5RequestError(message)


def _connection_error_message(code: int, desc: str, *, path: str | None, login: int | None, server: str | None) -> str:
    return (
        f"MetaTrader5.initialize() failed: ({code}) {desc}\n"
        "Likely causes:\n"
        "  - the MT5 terminal is not running\n"
        f"  - MT5_PATH is wrong (path={path or '<unset: attaching to a running terminal>'})\n"
        f"  - login/server/password is wrong (login={login or '<unset>'}, server={server or '<unset>'})\n"
        "  - the terminal is running but not logged in to any account\n"
        "  - the terminal failed to initialize (e.g. still starting up, or AutoTrading disabled)"
    )


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def connect(
    path: str | None = None,
    login: int | None = None,
    password: str | None = None,
    server: str | None = None,
    timeout_ms: int = 10000,
) -> bool:
    """Initialize the MT5 terminal connection. Falls back to MT5_* env vars when args are omitted."""
    global _connected
    mt5 = _get_mt5()

    path = path or os.environ.get("MT5_PATH") or None
    login = login if login is not None else _env_int("MT5_LOGIN")
    password = password or os.environ.get("MT5_PASSWORD") or None
    server = server or os.environ.get("MT5_SERVER") or None

    kwargs: dict[str, Any] = {"timeout": timeout_ms}
    if login is not None:
        kwargs["login"] = login
    if password is not None:
        kwargs["password"] = password
    if server is not None:
        kwargs["server"] = server

    ok = mt5.initialize(path, **kwargs) if path else mt5.initialize(**kwargs)
    if not ok:
        code, desc = mt5.last_error()
        raise MT5ConnectionError(_connection_error_message(code, desc, path=path, login=login, server=server))

    _connected = True
    logger.info("Connected to MT5 terminal (login=%s, server=%s)", login or "<default>", server or "<default>")
    return True


def is_connected() -> bool:
    if not _connected:
        return False
    mt5 = _get_mt5()
    return mt5.terminal_info() is not None


def ensure_connected() -> None:
    if not is_connected():
        connect()


def shutdown() -> None:
    """Release the MT5 terminal connection."""
    global _connected
    mt5 = _get_mt5()
    mt5.shutdown()
    _connected = False
    logger.info("Disconnected from MT5 terminal")


# --- SAFE_READ wrappers -----------------------------------------------------

def get_account_info() -> dict:
    ensure_connected()
    mt5 = _get_mt5()
    info = mt5.account_info()
    if info is None:
        _raise_last_error(mt5, "account_info")
    return mt5_struct_to_dict(info)


def get_terminal_info() -> dict:
    ensure_connected()
    mt5 = _get_mt5()
    info = mt5.terminal_info()
    if info is None:
        _raise_last_error(mt5, "terminal_info")
    return mt5_struct_to_dict(info)


def get_symbol_info(symbol: str) -> dict:
    ensure_connected()
    mt5 = _get_mt5()
    mt5.symbol_select(symbol, True)  # MT5 only returns data for symbols visible in Market Watch
    info = mt5.symbol_info(symbol)
    if info is None:
        _raise_last_error(mt5, f"symbol_info({symbol})", symbol=symbol)
    return mt5_struct_to_dict(info)


def get_tick(symbol: str) -> dict:
    ensure_connected()
    mt5 = _get_mt5()
    mt5.symbol_select(symbol, True)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        _raise_last_error(mt5, f"symbol_info_tick({symbol})", symbol=symbol)
    return mt5_struct_to_dict(tick)


def _resolve_timeframe(mt5: Any, timeframe: str) -> int:
    const_name = f"TIMEFRAME_{timeframe.strip().upper()}"
    if not hasattr(mt5, const_name):
        raise ValueError(
            f"Unknown timeframe '{timeframe}'. Expected one of e.g. M1, M5, M15, M30, H1, H4, D1, W1, MN1."
        )
    return getattr(mt5, const_name)


def _rates_to_list(rates: Any) -> list[dict]:
    if rates is None:
        return []
    if hasattr(rates, "dtype") and getattr(rates.dtype, "names", None):
        names = rates.dtype.names
        return [{name: row[name].item() for name in names} for row in rates]
    return [row._asdict() if hasattr(row, "_asdict") else dict(row) for row in rates]


def get_rates(symbol: str, timeframe: str, count: int = 100, start_pos: int = 0) -> list[dict]:
    ensure_connected()
    mt5 = _get_mt5()
    tf_const = _resolve_timeframe(mt5, timeframe)
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, tf_const, start_pos, count)
    if rates is None:
        _raise_last_error(mt5, f"copy_rates_from_pos({symbol}, {timeframe})", symbol=symbol)
    return _rates_to_list(rates)


def get_positions(symbol: str | None = None, ticket: int | None = None) -> list[dict]:
    ensure_connected()
    mt5 = _get_mt5()
    if ticket is not None:
        result = mt5.positions_get(ticket=ticket)
    elif symbol:
        result = mt5.positions_get(symbol=symbol)
    else:
        result = mt5.positions_get()
    if result is None:
        _raise_last_error(mt5, "positions_get")
    return mt5_struct_to_dict(result)


def get_orders(symbol: str | None = None, ticket: int | None = None) -> list[dict]:
    ensure_connected()
    mt5 = _get_mt5()
    if ticket is not None:
        result = mt5.orders_get(ticket=ticket)
    elif symbol:
        result = mt5.orders_get(symbol=symbol)
    else:
        result = mt5.orders_get()
    if result is None:
        _raise_last_error(mt5, "orders_get")
    return mt5_struct_to_dict(result)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Cannot parse datetime from {value!r}")


def get_history_deals(
    date_from: Any = None,
    date_to: Any = None,
    *,
    ticket: int | None = None,
    position: int | None = None,
    group: str | None = None,
) -> list[dict]:
    ensure_connected()
    mt5 = _get_mt5()
    if ticket is not None:
        result = mt5.history_deals_get(ticket=ticket)
    elif position is not None:
        result = mt5.history_deals_get(position=position)
    else:
        dt_from = _parse_datetime(date_from) if date_from else datetime(1970, 1, 1)
        dt_to = _parse_datetime(date_to) if date_to else datetime.now()
        kwargs = {"group": group} if group else {}
        result = mt5.history_deals_get(dt_from, dt_to, **kwargs)
    if result is None:
        _raise_last_error(mt5, "history_deals_get")
    return mt5_struct_to_dict(result)


# --- Order planning calculations (no execution) -----------------------------
# These call MT5's own dry-run calculators (order_calc_margin / order_calc_profit /
# order_check). None of them place, modify, or cancel an order.

def resolve_order_type(order_type: str) -> int:
    mt5 = _get_mt5()
    const_name = f"ORDER_TYPE_{order_type.strip().upper()}"
    if not hasattr(mt5, const_name):
        raise ValueError(
            f"Unknown order type '{order_type}'. Expected one of: BUY, SELL, BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP."
        )
    return getattr(mt5, const_name)


def calc_margin(order_type: str, symbol: str, volume: float, price: float) -> float:
    ensure_connected()
    mt5 = _get_mt5()
    action = resolve_order_type(order_type)
    margin = mt5.order_calc_margin(action, symbol, volume, price)
    if margin is None:
        _raise_last_error(mt5, "order_calc_margin")
    return float(margin)


def calc_profit(order_type: str, symbol: str, volume: float, price_open: float, price_close: float) -> float:
    ensure_connected()
    mt5 = _get_mt5()
    action = resolve_order_type(order_type)
    profit = mt5.order_calc_profit(action, symbol, volume, price_open, price_close)
    if profit is None:
        _raise_last_error(mt5, "order_calc_profit")
    return float(profit)


def order_check(request: dict) -> dict:
    """Server-side dry-run validation of an order request. Never sends the order."""
    ensure_connected()
    mt5 = _get_mt5()
    result = mt5.order_check(request)
    if result is None:
        _raise_last_error(mt5, "order_check")
    return mt5_struct_to_dict(result)
