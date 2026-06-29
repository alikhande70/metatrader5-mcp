"""Strategy Tester adapter: prepare configs, import CSV exports, review/compare runs.

Everything here is read/analysis/draft. `prepare_signal_only_test` builds a tester
`.ini` draft (no execution). `import_csv` reads exported CSVs confined to the reports
directory. `run_backtest_if_supported` is the gated runtime entry point: outside a
Windows MT5 runtime it returns a structured ``UNSUPPORTED_IN_THIS_ENVIRONMENT`` payload.

No tool here runs live trading or touches a real account.
"""

from __future__ import annotations

import csv
import sys
from io import StringIO
from typing import Any

from .paths import env_base_dir, resolve_within

UNSUPPORTED = "UNSUPPORTED_IN_THIS_ENVIRONMENT"
REQUIRES_WINDOWS = "REQUIRES_WINDOWS_MT5_RUNTIME"


def _reports_dir():
    return env_base_dir("MT5_MCP_REPORTS_DIR", "reports")


def prepare_signal_only_test(
    expert: str,
    symbol: str,
    timeframe: str = "H1",
    date_from: str = "2023.01.01",
    date_to: str = "2023.12.31",
    deposit: float = 10000.0,
    model: int = 1,
) -> dict[str, Any]:
    """Build a Strategy Tester `.ini` config draft for a signal-only / non-live test (no execution)."""
    ini = (
        "[Tester]\n"
        f"Expert={expert}\n"
        f"Symbol={symbol}\n"
        f"Period={timeframe}\n"
        f"Model={model}\n"
        f"FromDate={date_from}\n"
        f"ToDate={date_to}\n"
        f"Deposit={deposit}\n"
        "Optimization=0\n"
        "ExecutionMode=0\n"
        "; Signal-only: the EA itself must implement a non-trading/signal mode.\n"
        "; This bridge does not enable live trading.\n"
    )
    return {
        "expert": expert,
        "symbol": symbol,
        "timeframe": timeframe,
        "ini": ini,
        "note": "Config draft only. The bridge does not launch live trading; run the test in MetaTrader 5.",
    }


def run_backtest_if_supported(config_ini: str | None = None) -> dict[str, Any]:
    """Run a backtest if a Windows MT5 runtime is available; otherwise return a gated payload."""
    if sys.platform != "win32":
        return {
            "status": UNSUPPORTED,
            "reason": REQUIRES_WINDOWS,
            "note": "Strategy Tester runs inside MetaTrader 5 on Windows. Prepare a config with "
            "tester_prepare_signal_only_test and run it in the terminal, then import results.",
        }
    # Even on Windows, automated tester launch is intentionally out of scope for this
    # phase; the owner runs the test in the terminal and imports the exported report.
    return {
        "status": "not_implemented_in_this_phase",
        "note": "Automated tester launch is gated to a future phase. Run the test in MetaTrader 5 and import the report.",
    }


def _parse_csv(text: str) -> dict[str, Any]:
    # Sniff delimiter; MT5 exports use ';' or ',' or tab depending on locale.
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.reader(StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return {"delimiter": delimiter, "header": [], "rows": [], "row_count": 0}
    header = rows[0]
    data = [dict(zip(header, r)) for r in rows[1:]]
    return {"delimiter": delimiter, "header": header, "rows": data, "row_count": len(data)}


def import_csv(path: str) -> dict[str, Any]:
    """Import an exported Strategy Tester CSV (journal/trades/performance), confined to the reports dir."""
    target = resolve_within(_reports_dir(), path, allowed_suffixes=(".csv",), must_exist=True)
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = target.read_text(encoding="utf-16")
    parsed = _parse_csv(text)
    return {"path": path, "absolute_path": str(target), **parsed}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def review_results(summary: dict[str, Any]) -> dict[str, Any]:
    """Normalise and flag a parsed Strategy Tester summary dict (from read_strategy_report)."""
    def pick(*keys: str) -> Any:
        for k in keys:
            for sk, sv in summary.items():
                if sk.lower() == k.lower():
                    return sv
        return None

    profit_factor = _to_float(pick("Profit factor", "ProfitFactor"))
    net_profit = _to_float(pick("Total net profit", "Net profit"))
    max_dd = _to_float(pick("Maximal drawdown", "Equity drawdown maximal", "Drawdown"))
    trades = _to_float(pick("Total trades", "Trades"))

    flags: list[str] = []
    if profit_factor is not None and profit_factor < 1.0:
        flags.append("Profit factor below 1.0 - strategy is net-losing on this run.")
    if trades is not None and trades < 30:
        flags.append("Fewer than 30 trades - results may not be statistically meaningful.")
    if net_profit is not None and net_profit <= 0:
        flags.append("Net profit is non-positive.")

    return {
        "metrics": {
            "profit_factor": profit_factor,
            "net_profit": net_profit,
            "max_drawdown": max_dd,
            "total_trades": trades,
        },
        "flags": flags or ["No basic red flags detected."],
    }


def compare_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare several reviewed runs (each a dict with a `metrics` block or a raw summary)."""
    normalized = []
    for i, run in enumerate(runs):
        metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else review_results(run)["metrics"]
        normalized.append({"index": i, "label": run.get("label", f"run_{i}"), **metrics})

    def best_by(key: str, *, highest: bool = True) -> Any:
        candidates = [r for r in normalized if r.get(key) is not None]
        if not candidates:
            return None
        return (max if highest else min)(candidates, key=lambda r: r[key])["label"]

    return {
        "runs": normalized,
        "best_profit_factor": best_by("profit_factor"),
        "best_net_profit": best_by("net_profit"),
        "lowest_drawdown": best_by("max_drawdown", highest=False),
    }


def generate_backtest_report(review: dict[str, Any], title: str = "Backtest Review") -> dict[str, Any]:
    """Render a reviewed result into a concise Markdown report string (draft)."""
    metrics = review.get("metrics", {})
    flags = review.get("flags", [])
    lines = [f"# {title}", "", "## Metrics"]
    for key, value in metrics.items():
        lines.append(f"- **{key}**: {value}")
    lines += ["", "## Flags"]
    lines += [f"- {flag}" for flag in flags]
    return {"title": title, "markdown": "\n".join(lines)}
