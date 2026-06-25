from __future__ import annotations

import pytest

from mt5_mcp import order_tools
from mt5_mcp.risk_guard import RiskGuardError


def test_order_tools_blocked_by_default_even_on_demo(fake_mt5, monkeypatch):
    monkeypatch.delenv("MT5_MCP_ENABLE_DEMO_TRADING", raising=False)
    with pytest.raises(RiskGuardError):
        order_tools.calculate_margin("BUY", "EURUSD", 0.1, 1.10)


def test_order_tools_blocked_on_real_account_even_if_demo_trading_enabled(fake_mt5, monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    fake_mt5.account = fake_mt5.account._replace(trade_mode=fake_mt5.ACCOUNT_TRADE_MODE_REAL)
    with pytest.raises(RiskGuardError):
        order_tools.prepare_order_plan("BUY", "EURUSD", 0.1, 1.10, sl=1.09, tp=1.12)


def test_calculate_margin_on_enabled_demo(fake_mt5, monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    result = order_tools.calculate_margin("BUY", "EURUSD", 0.1, 1.10)
    assert result["required_margin"] == 100.0
    assert result["symbol"] == "EURUSD"


def test_calculate_profit_on_enabled_demo(fake_mt5, monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    result = order_tools.calculate_profit("BUY", "EURUSD", 0.1, 1.10, 1.12)
    assert result["estimated_profit"] == 50.0


def test_check_order_never_sends(fake_mt5, monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    result = order_tools.check_order("BUY", "EURUSD", 0.1, 1.10, sl=1.09, tp=1.12)
    assert result["sent"] is False
    assert "request" in result
    assert result["check_result"]["retcode"] == 0
    assert not hasattr(fake_mt5, "order_send")


def test_build_order_request_market_vs_pending(fake_mt5, monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    market_request = order_tools.build_order_request("BUY", "EURUSD", 0.1, 1.10)
    assert market_request["action"] == fake_mt5.TRADE_ACTION_DEAL

    pending_request = order_tools.build_order_request("BUY_LIMIT", "EURUSD", 0.1, 1.05)
    assert pending_request["action"] == fake_mt5.TRADE_ACTION_PENDING


def test_prepare_order_plan_is_never_sent_and_marked_planned(fake_mt5, monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    plan = order_tools.prepare_order_plan("BUY", "EURUSD", 0.1, 1.10, sl=1.09, tp=1.12)

    assert plan["status"] == "PLANNED_NOT_SENT"
    assert plan["required_margin"] == 100.0
    assert plan["estimated_profit_at_tp"] == 50.0
    assert plan["estimated_loss_at_sl"] == 50.0  # fake order_calc_profit always returns profit_result
    assert plan["order_check_result"]["retcode"] == 0
    assert "plan_id" in plan
    assert not hasattr(fake_mt5, "order_send")
