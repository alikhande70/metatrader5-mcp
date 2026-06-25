from __future__ import annotations

import pytest

from mt5_mcp import mt5_bridge
from tests.conftest import Deal, Order, Position


def test_mt5_not_available_raises_clear_error(monkeypatch):
    monkeypatch.setattr(mt5_bridge, "_mt5_module", None)
    with pytest.raises(mt5_bridge.MT5NotAvailableError):
        mt5_bridge._get_mt5()


def test_connect_sets_connected_flag(fake_mt5):
    assert mt5_bridge.connect() is True
    assert mt5_bridge.is_connected() is True


def test_get_account_info_returns_plain_dict(fake_mt5):
    info = mt5_bridge.get_account_info()
    assert isinstance(info, dict)
    assert info["login"] == 12345
    assert info["trade_mode"] == 0


def test_get_terminal_info(fake_mt5):
    info = mt5_bridge.get_terminal_info()
    assert info["data_path"] == "/fake/mt5/data"


def test_get_symbol_info_known_symbol(fake_mt5):
    info = mt5_bridge.get_symbol_info("EURUSD")
    assert info["name"] == "EURUSD"
    assert info["digits"] == 5


def test_get_symbol_info_unknown_symbol_raises(fake_mt5):
    with pytest.raises(mt5_bridge.MT5RequestError):
        mt5_bridge.get_symbol_info("DOESNOTEXIST")


def test_get_tick(fake_mt5):
    tick = mt5_bridge.get_tick("EURUSD")
    assert tick["bid"] == 1.1000
    assert tick["ask"] == 1.1002


def test_get_rates_with_plain_dict_rows(fake_mt5):
    fake_mt5.rates["EURUSD"] = [
        {"time": 1700000000, "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "tick_volume": 100},
        {"time": 1700003600, "open": 1.105, "high": 1.108, "low": 1.10, "close": 1.107, "tick_volume": 120},
    ]
    rates = mt5_bridge.get_rates("EURUSD", "H1", count=2)
    assert len(rates) == 2
    assert rates[0]["close"] == 1.105


def test_get_rates_unknown_timeframe_raises(fake_mt5):
    with pytest.raises(ValueError):
        mt5_bridge.get_rates("EURUSD", "NOT_A_TIMEFRAME")


def test_get_positions_filters_by_symbol(fake_mt5):
    fake_mt5.positions = [
        Position(1, "EURUSD", 0.1, 0, 1.10, 1.11, 1.09, 1.12, 10.0, -0.5, 1700000000),
        Position(2, "GBPUSD", 0.2, 1, 1.30, 1.29, 1.31, 1.27, -5.0, 0.0, 1700000100),
    ]
    all_positions = mt5_bridge.get_positions()
    assert len(all_positions) == 2

    eur_only = mt5_bridge.get_positions(symbol="EURUSD")
    assert len(eur_only) == 1
    assert eur_only[0]["symbol"] == "EURUSD"


def test_get_orders(fake_mt5):
    fake_mt5.orders = [Order(10, "EURUSD", 0.1, 2, 1.05, 1.04, 1.08, 1700000000)]
    orders = mt5_bridge.get_orders()
    assert len(orders) == 1
    assert orders[0]["ticket"] == 10


def test_get_history_deals_by_date_range(fake_mt5):
    fake_mt5.deals = [
        Deal(100, 1, 1700000000, 0, 0, "EURUSD", 0.1, 1.10, 0.0, 0.0, 0.0),
        Deal(101, 1, 1700003600, 0, 1, "EURUSD", 0.1, 1.12, 20.0, -0.5, -0.2),
    ]
    deals = mt5_bridge.get_history_deals("2023-01-01", "2023-12-31")
    assert len(deals) == 2
    assert deals[1]["profit"] == 20.0


def test_get_history_deals_by_ticket(fake_mt5):
    fake_mt5.deals = [Deal(100, 1, 1700000000, 0, 0, "EURUSD", 0.1, 1.10, 0.0, 0.0, 0.0)]
    deals = mt5_bridge.get_history_deals(ticket=100)
    assert len(deals) == 1


def test_calc_margin_and_profit(fake_mt5):
    margin = mt5_bridge.calc_margin("BUY", "EURUSD", 0.1, 1.10)
    assert margin == 100.0
    profit = mt5_bridge.calc_profit("BUY", "EURUSD", 0.1, 1.10, 1.12)
    assert profit == 50.0


def test_resolve_order_type_unknown_raises(fake_mt5):
    with pytest.raises(ValueError):
        mt5_bridge.resolve_order_type("NOT_A_TYPE")


def test_order_check_never_calls_order_send(fake_mt5):
    assert not hasattr(fake_mt5, "order_send")
    result = mt5_bridge.order_check({"action": fake_mt5.TRADE_ACTION_DEAL, "symbol": "EURUSD"})
    assert result["retcode"] == 0
