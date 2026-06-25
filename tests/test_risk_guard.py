from __future__ import annotations

import pytest

from mt5_mcp.risk_guard import (
    ACCOUNT_TRADE_MODE_DEMO,
    ACCOUNT_TRADE_MODE_REAL,
    RiskGuardError,
    guard_order_tool,
    is_demo_trading_enabled,
    is_live_account,
)


def test_demo_trading_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MT5_MCP_ENABLE_DEMO_TRADING", raising=False)
    assert is_demo_trading_enabled() is False


def test_demo_trading_enabled_via_env(monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    assert is_demo_trading_enabled() is True


def test_is_live_account():
    assert is_live_account({"trade_mode": ACCOUNT_TRADE_MODE_REAL}) is True
    assert is_live_account({"trade_mode": ACCOUNT_TRADE_MODE_DEMO}) is False


def test_demo_account_blocked_by_default(monkeypatch):
    monkeypatch.delenv("MT5_MCP_ENABLE_DEMO_TRADING", raising=False)
    with pytest.raises(RiskGuardError):
        guard_order_tool({"trade_mode": ACCOUNT_TRADE_MODE_DEMO}, "calculate_margin")


def test_demo_account_allowed_when_enabled(monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    guard_order_tool({"trade_mode": ACCOUNT_TRADE_MODE_DEMO}, "calculate_margin")  # should not raise


def test_real_account_always_blocked_even_if_demo_trading_enabled(monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    with pytest.raises(RiskGuardError):
        guard_order_tool({"trade_mode": ACCOUNT_TRADE_MODE_REAL}, "prepare_order_plan")


def test_contest_account_always_blocked(monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    with pytest.raises(RiskGuardError):
        guard_order_tool({"trade_mode": 1}, "check_order")


def test_real_account_message_mentions_trade_mode_and_no_override(monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    with pytest.raises(RiskGuardError) as exc_info:
        guard_order_tool({"trade_mode": ACCOUNT_TRADE_MODE_REAL}, "calculate_margin")
    msg = str(exc_info.value)
    assert "real" in msg
    assert "always blocked" in msg
    assert "no override" in msg


def test_demo_disabled_message_mentions_env_var(monkeypatch):
    monkeypatch.delenv("MT5_MCP_ENABLE_DEMO_TRADING", raising=False)
    with pytest.raises(RiskGuardError) as exc_info:
        guard_order_tool({"trade_mode": ACCOUNT_TRADE_MODE_DEMO}, "calculate_margin")
    msg = str(exc_info.value)
    assert "MT5_MCP_ENABLE_DEMO_TRADING" in msg
    assert "demo" in msg


def test_unknown_trade_mode_message_says_unknown(monkeypatch):
    monkeypatch.setenv("MT5_MCP_ENABLE_DEMO_TRADING", "true")
    with pytest.raises(RiskGuardError) as exc_info:
        guard_order_tool({"trade_mode": 99}, "check_order")
    msg = str(exc_info.value)
    assert "unknown" in msg
