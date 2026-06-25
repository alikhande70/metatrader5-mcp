"""SAFE_ANALYSIS tools: pure computations over data already read from MT5.

None of these functions touch the MT5 connection - they take plain dicts/lists
(as returned by mt5_bridge) or raw numbers, and return plain dicts. That is
what makes them safe to classify as SAFE_ANALYSIS rather than REQUIRES_APPROVAL.
"""

from __future__ import annotations

from typing import Any

POSITION_TYPE_NAMES = {0: "buy", 1: "sell"}

# DEAL_TYPE_BUY / DEAL_TYPE_SELL - excludes balance/credit/other non-trade deals.
TRADE_DEAL_TYPES = {0, 1}
# DEAL_ENTRY_OUT / DEAL_ENTRY_INOUT / DEAL_ENTRY_OUT_BY - deals that close volume
# and therefore carry a realized profit (opening deals have profit == 0).
CLOSING_DEAL_ENTRIES = {1, 2, 3}


def summarize_positions(positions: list[dict]) -> dict:
    """Aggregate open positions by total, by symbol, and by side (buy/sell)."""
    total_volume = 0.0
    total_profit = 0.0
    total_swap = 0.0
    by_symbol: dict[str, dict[str, float]] = {}
    by_type = {
        "buy": {"count": 0, "volume": 0.0, "profit": 0.0},
        "sell": {"count": 0, "volume": 0.0, "profit": 0.0},
    }

    for pos in positions:
        volume = float(pos.get("volume", 0))
        profit = float(pos.get("profit", 0))
        swap = float(pos.get("swap", 0))
        symbol = pos.get("symbol", "UNKNOWN")
        side = POSITION_TYPE_NAMES.get(pos.get("type"), "unknown")

        total_volume += volume
        total_profit += profit
        total_swap += swap

        bucket = by_symbol.setdefault(symbol, {"count": 0, "volume": 0.0, "profit": 0.0})
        bucket["count"] += 1
        bucket["volume"] += volume
        bucket["profit"] += profit

        if side in by_type:
            by_type[side]["count"] += 1
            by_type[side]["volume"] += volume
            by_type[side]["profit"] += profit

    return {
        "total_positions": len(positions),
        "total_volume": round(total_volume, 4),
        "total_profit": round(total_profit, 2),
        "total_swap": round(total_swap, 2),
        "by_symbol": {
            symbol: {**bucket, "volume": round(bucket["volume"], 4), "profit": round(bucket["profit"], 2)}
            for symbol, bucket in by_symbol.items()
        },
        "by_type": {
            side: {**bucket, "volume": round(bucket["volume"], 4), "profit": round(bucket["profit"], 2)}
            for side, bucket in by_type.items()
        },
    }


def analyze_drawdown(deals: list[dict], starting_balance: float = 0.0, include_curve: bool = False) -> dict:
    """Basic peak-to-trough drawdown over a chronological sequence of closed deals."""
    sorted_deals = sorted(deals, key=lambda d: d.get("time", 0))

    balance = starting_balance
    peak = starting_balance
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    curve = []

    for deal in sorted_deals:
        change = float(deal.get("profit", 0)) + float(deal.get("swap", 0)) + float(deal.get("commission", 0))
        balance += change
        peak = max(peak, balance)
        drawdown = peak - balance
        drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)
        if include_curve:
            curve.append({"time": deal.get("time"), "balance": round(balance, 2)})

    result = {
        "starting_balance": round(starting_balance, 2),
        "ending_balance": round(balance, 2),
        "peak_balance": round(peak, 2),
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "num_deals": len(sorted_deals),
    }
    if include_curve:
        result["equity_curve"] = curve
    return result


def analyze_trade_history(deals: list[dict]) -> dict:
    """Basic win rate / profit factor stats from closed (history) deals."""
    trades = [d for d in deals if d.get("type") in TRADE_DEAL_TYPES and d.get("entry") in CLOSING_DEAL_ENTRIES]

    total_trades = len(trades)
    wins = [t for t in trades if float(t.get("profit", 0)) > 0]
    losses = [t for t in trades if float(t.get("profit", 0)) < 0]
    breakeven = [t for t in trades if float(t.get("profit", 0)) == 0]

    gross_profit = sum(float(t.get("profit", 0)) for t in wins)
    gross_loss = sum(float(t.get("profit", 0)) for t in losses)  # negative or zero
    net_profit = gross_profit + gross_loss

    win_rate = (len(wins) / total_trades * 100) if total_trades else 0.0
    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    profit_factor = round(gross_profit / abs(gross_loss), 4) if gross_loss != 0 else None

    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate_pct": round(win_rate, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "net_profit": round(net_profit, 2),
        "profit_factor": profit_factor,
        "average_win": round(avg_win, 2),
        "average_loss": round(avg_loss, 2),
    }


def calculate_profit_risk_basic(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    volume: float = 1.0,
    value_per_point: float | None = None,
) -> dict[str, Any]:
    """Pure price-math risk/reward calculation. No symbol lookup, no MT5 connection needed."""
    risk_points = abs(entry_price - stop_loss)
    reward_points = abs(take_profit - entry_price)
    risk_reward_ratio = (reward_points / risk_points) if risk_points else None

    result: dict[str, Any] = {
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "volume": volume,
        "risk_points": round(risk_points, 6),
        "reward_points": round(reward_points, 6),
        "risk_reward_ratio": round(risk_reward_ratio, 4) if risk_reward_ratio is not None else None,
    }
    if value_per_point is not None:
        result["estimated_risk_amount"] = round(risk_points * volume * value_per_point, 2)
        result["estimated_reward_amount"] = round(reward_points * volume * value_per_point, 2)
    return result
