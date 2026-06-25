"""Shared test fixtures: a fake MetaTrader5 module so tests run without a real terminal."""

from __future__ import annotations

from collections import namedtuple

import pytest

AccountInfo = namedtuple(
    "AccountInfo",
    ["login", "balance", "equity", "margin", "margin_free", "leverage", "currency", "trade_mode", "server"],
)
TerminalInfo = namedtuple(
    "TerminalInfo", ["community_account", "connected", "trade_allowed", "data_path", "build"]
)
SymbolInfo = namedtuple(
    "SymbolInfo",
    ["name", "point", "digits", "spread", "volume_min", "volume_max", "volume_step", "trade_contract_size"],
)
Tick = namedtuple("Tick", ["time", "bid", "ask", "last", "volume"])
Position = namedtuple(
    "Position",
    ["ticket", "symbol", "volume", "type", "price_open", "price_current", "sl", "tp", "profit", "swap", "time"],
)
Order = namedtuple("Order", ["ticket", "symbol", "volume_current", "type", "price_open", "sl", "tp", "time_setup"])
Deal = namedtuple(
    "Deal",
    ["ticket", "order", "time", "type", "entry", "symbol", "volume", "price", "profit", "swap", "commission"],
)
OrderCheckResult = namedtuple(
    "OrderCheckResult", ["retcode", "balance", "equity", "profit", "margin", "margin_free", "margin_level", "comment"]
)


class FakeMT5:
    """Minimal stand-in for the `MetaTrader5` module covering everything mt5_bridge uses."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 16385
    TIMEFRAME_D1 = 16408

    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5

    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1

    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2

    def __init__(self) -> None:
        self.initialized = False
        self._last_error = (1, "Success")
        self.account = AccountInfo(
            login=12345,
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            margin_free=10000.0,
            leverage=100,
            currency="USD",
            trade_mode=self.ACCOUNT_TRADE_MODE_DEMO,
            server="Demo-Server",
        )
        self.terminal = TerminalInfo(
            community_account=False, connected=True, trade_allowed=True, data_path="/fake/mt5/data", build=4100
        )
        self.symbols: dict[str, SymbolInfo] = {
            "EURUSD": SymbolInfo("EURUSD", 0.00001, 5, 10, 0.01, 100.0, 0.01, 100000.0),
        }
        self.ticks: dict[str, Tick] = {
            "EURUSD": Tick(time=1700000000, bid=1.1000, ask=1.1002, last=1.1001, volume=1),
        }
        self.rates: dict[str, list] = {}
        self.positions: list[Position] = []
        self.orders: list[Order] = []
        self.deals: list[Deal] = []
        self.margin_result: float | None = 100.0
        self.profit_result: float | None = 50.0
        self.check_result: OrderCheckResult | None = OrderCheckResult(0, 10000.0, 10000.0, 0.0, 100.0, 9900.0, 9900.0, "ok")

    def initialize(self, *args, **kwargs) -> bool:
        self.initialized = True
        return True

    def shutdown(self) -> None:
        self.initialized = False

    def last_error(self):
        return self._last_error

    def terminal_info(self):
        return self.terminal if self.initialized else None

    def account_info(self):
        return self.account

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        return True

    def symbol_info(self, symbol: str):
        return self.symbols.get(symbol)

    def symbol_info_tick(self, symbol: str):
        return self.ticks.get(symbol)

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        return self.rates.get(symbol, [])

    def positions_get(self, symbol=None, ticket=None):
        if ticket is not None:
            return tuple(p for p in self.positions if p.ticket == ticket)
        if symbol is not None:
            return tuple(p for p in self.positions if p.symbol == symbol)
        return tuple(self.positions)

    def orders_get(self, symbol=None, ticket=None):
        if ticket is not None:
            return tuple(o for o in self.orders if o.ticket == ticket)
        if symbol is not None:
            return tuple(o for o in self.orders if o.symbol == symbol)
        return tuple(self.orders)

    def history_deals_get(self, *args, ticket=None, position=None, group=None):
        if ticket is not None:
            return tuple(d for d in self.deals if d.ticket == ticket)
        if position is not None:
            return tuple(d for d in self.deals if getattr(d, "position_id", None) == position)
        return tuple(self.deals)

    def order_calc_margin(self, action, symbol, volume, price):
        return self.margin_result

    def order_calc_profit(self, action, symbol, volume, price_open, price_close):
        return self.profit_result

    def order_check(self, request: dict):
        return self.check_result


@pytest.fixture()
def fake_mt5(monkeypatch):
    """Inject a FakeMT5 instance as mt5_bridge's module-level mt5 handle."""
    from mt5_mcp import mt5_bridge

    fake = FakeMT5()
    monkeypatch.setattr(mt5_bridge, "_mt5_module", fake)
    monkeypatch.setattr(mt5_bridge, "_connected", False)
    return fake
