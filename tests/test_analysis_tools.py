from __future__ import annotations

from mt5_mcp import analysis_tools


def test_summarize_positions_aggregates_by_symbol_and_side():
    positions = [
        {"symbol": "EURUSD", "volume": 0.1, "type": 0, "profit": 10.0, "swap": -0.1},
        {"symbol": "EURUSD", "volume": 0.2, "type": 1, "profit": -5.0, "swap": 0.0},
        {"symbol": "GBPUSD", "volume": 0.3, "type": 0, "profit": 2.0, "swap": 0.0},
    ]
    summary = analysis_tools.summarize_positions(positions)
    assert summary["total_positions"] == 3
    assert summary["total_volume"] == 0.6
    assert summary["total_profit"] == 7.0
    assert summary["by_symbol"]["EURUSD"]["count"] == 2
    assert summary["by_type"]["buy"]["count"] == 2
    assert summary["by_type"]["sell"]["count"] == 1


def test_summarize_positions_empty():
    summary = analysis_tools.summarize_positions([])
    assert summary["total_positions"] == 0
    assert summary["total_profit"] == 0.0


def test_analyze_drawdown_basic_sequence():
    # balance: 1000 -> 1100 (peak) -> 1050 (drawdown 50) -> 1150 (new peak)
    deals = [
        {"time": 1, "profit": 100.0, "swap": 0.0, "commission": 0.0},
        {"time": 2, "profit": -50.0, "swap": 0.0, "commission": 0.0},
        {"time": 3, "profit": 100.0, "swap": 0.0, "commission": 0.0},
    ]
    result = analysis_tools.analyze_drawdown(deals, starting_balance=1000.0)
    assert result["starting_balance"] == 1000.0
    assert result["ending_balance"] == 1150.0
    assert result["peak_balance"] == 1150.0
    assert result["max_drawdown"] == 50.0
    assert result["num_deals"] == 3


def test_analyze_drawdown_include_curve():
    deals = [{"time": 1, "profit": 10.0, "swap": 0.0, "commission": 0.0}]
    result = analysis_tools.analyze_drawdown(deals, starting_balance=0.0, include_curve=True)
    assert "equity_curve" in result
    assert result["equity_curve"][0]["balance"] == 10.0


def test_analyze_trade_history_win_rate_and_profit_factor():
    deals = [
        {"type": 0, "entry": 0, "profit": 0.0},  # opening leg, excluded
        {"type": 0, "entry": 1, "profit": 100.0},  # win
        {"type": 1, "entry": 1, "profit": -40.0},  # loss
        {"type": 0, "entry": 1, "profit": 20.0},  # win
        {"type": 2, "entry": 1, "profit": 500.0},  # balance deal, excluded (type 2 not BUY/SELL)
    ]
    result = analysis_tools.analyze_trade_history(deals)
    assert result["total_trades"] == 3
    assert result["wins"] == 2
    assert result["losses"] == 1
    assert result["gross_profit"] == 120.0
    assert result["gross_loss"] == -40.0
    assert result["profit_factor"] == 3.0
    assert round(result["win_rate_pct"], 2) == 66.67


def test_analyze_trade_history_no_losses_gives_none_profit_factor():
    deals = [{"type": 0, "entry": 1, "profit": 50.0}]
    result = analysis_tools.analyze_trade_history(deals)
    assert result["profit_factor"] is None


def test_calculate_profit_risk_basic_ratio():
    result = analysis_tools.calculate_profit_risk_basic(entry_price=1.10, stop_loss=1.09, take_profit=1.12)
    assert round(result["risk_points"], 4) == 0.01
    assert round(result["reward_points"], 4) == 0.02
    assert result["risk_reward_ratio"] == 2.0


def test_calculate_profit_risk_basic_with_value_per_point():
    result = analysis_tools.calculate_profit_risk_basic(
        entry_price=1.10, stop_loss=1.09, take_profit=1.12, volume=2.0, value_per_point=10.0
    )
    assert result["estimated_risk_amount"] == 0.2
    assert result["estimated_reward_amount"] == 0.4
