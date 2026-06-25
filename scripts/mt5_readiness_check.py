"""Read-only MetaTrader 5 readiness check.

This is a PLAIN diagnostic helper, NOT an MCP tool. It is never registered as
an MCP tool and is not exposed to any MCP client. Run it after setup to
confirm the environment is ready before pointing a client at the server:

    python scripts/mt5_readiness_check.py
    python scripts/mt5_readiness_check.py --symbol GBPUSD

What it does (read-only only):
  - checks the MetaTrader5 package is importable on this platform
  - connects to / initializes the running terminal
  - reads account info (and reports the detected trade mode)
  - reads terminal info
  - reads a symbol spec, a tick, and recent rates for one symbol
  - lists open positions and pending orders
  - reports the configured log and report directories

What it deliberately never does:
  - it never plans, sends, modifies, cancels, closes, or deletes any order
  - it never calls any REQUIRES_APPROVAL order-planning tool
  - it makes no writes to the terminal or its data folder

It prints a pass/fail table and exits non-zero only on clear readiness
failures (package unavailable, cannot connect, account/terminal unreadable).
Symbol/market-data and directory checks are reported as warnings, never as
hard failures, because a symbol may simply not be in Market Watch yet.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow running straight from a checkout (`python scripts/mt5_readiness_check.py`)
# even if the package was not installed with `pip install -e .` yet.
try:
    from mt5_mcp import log_reader, mt5_bridge, report_reader
except ModuleNotFoundError:  # pragma: no cover - convenience fallback
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from mt5_mcp import log_reader, mt5_bridge, report_reader

from mt5_mcp.report_reader import DEFAULT_REPORTS_DIRNAME

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def _trade_mode_name(account: dict) -> str:
    names = {0: "demo", 1: "contest", 2: "real"}
    return names.get(account.get("trade_mode"), f"unknown({account.get('trade_mode')!r})")


def run_checks(symbol: str = "EURUSD") -> list[CheckResult]:
    """Run all read-only readiness checks and return their results, in order."""
    results: list[CheckResult] = []

    # 1. MetaTrader5 package availability (critical).
    try:
        mt5_bridge.mt5_module()
    except mt5_bridge.MT5NotAvailableError as exc:
        results.append(CheckResult("MetaTrader5 package available", FAIL, str(exc).splitlines()[0]))
        results.append(CheckResult("Terminal connection (initialize)", SKIP, "skipped: package unavailable"))
        results.append(CheckResult("Account info", SKIP, "skipped: package unavailable"))
        results.append(CheckResult("Terminal info", SKIP, "skipped: package unavailable"))
        results.append(CheckResult(f"Symbol info ({symbol})", SKIP, "skipped: package unavailable"))
        results.append(CheckResult(f"Tick ({symbol})", SKIP, "skipped: package unavailable"))
        results.append(CheckResult(f"Rates ({symbol})", SKIP, "skipped: package unavailable"))
        results.append(CheckResult("Open positions", SKIP, "skipped: package unavailable"))
        results.append(CheckResult("Pending orders", SKIP, "skipped: package unavailable"))
        results.extend(_directory_checks())
        return results
    results.append(CheckResult("MetaTrader5 package available", PASS, f"importable on platform '{sys.platform}'"))

    # 2. Connection / initialize (critical).
    try:
        mt5_bridge.connect()
    except mt5_bridge.MT5ConnectionError as exc:
        results.append(CheckResult("Terminal connection (initialize)", FAIL, str(exc).splitlines()[0]))
        results.append(CheckResult("Account info", SKIP, "skipped: not connected"))
        results.append(CheckResult("Terminal info", SKIP, "skipped: not connected"))
        results.append(CheckResult(f"Symbol info ({symbol})", SKIP, "skipped: not connected"))
        results.append(CheckResult(f"Tick ({symbol})", SKIP, "skipped: not connected"))
        results.append(CheckResult(f"Rates ({symbol})", SKIP, "skipped: not connected"))
        results.append(CheckResult("Open positions", SKIP, "skipped: not connected"))
        results.append(CheckResult("Pending orders", SKIP, "skipped: not connected"))
        results.extend(_directory_checks())
        return results
    results.append(CheckResult("Terminal connection (initialize)", PASS, "initialize() succeeded"))

    # 3. Account info (critical) - also surfaces the trade mode.
    try:
        account = mt5_bridge.get_account_info()
        mode = _trade_mode_name(account)
        detail = f"login={account.get('login')} trade_mode={mode}"
        if mode in ("real", "contest"):
            detail += " (order planning is always blocked on this account)"
        results.append(CheckResult("Account info", PASS, detail))
    except Exception as exc:  # noqa: BLE001 - report any failure plainly
        results.append(CheckResult("Account info", FAIL, f"{type(exc).__name__}: {exc}"))

    # 4. Terminal info (critical).
    try:
        terminal = mt5_bridge.get_terminal_info()
        results.append(
            CheckResult(
                "Terminal info",
                PASS,
                f"connected={terminal.get('connected')} data_path={terminal.get('data_path')}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult("Terminal info", FAIL, f"{type(exc).__name__}: {exc}"))

    # 5-7. Market data for one symbol (warnings only - symbol may not be in Market Watch).
    try:
        info = mt5_bridge.get_symbol_info(symbol)
        results.append(CheckResult(f"Symbol info ({symbol})", PASS, f"digits={info.get('digits')}"))
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult(f"Symbol info ({symbol})", WARN, f"{type(exc).__name__}: {exc}"))

    try:
        tick = mt5_bridge.get_tick(symbol)
        results.append(CheckResult(f"Tick ({symbol})", PASS, f"bid={tick.get('bid')} ask={tick.get('ask')}"))
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult(f"Tick ({symbol})", WARN, f"{type(exc).__name__}: {exc}"))

    try:
        rates = mt5_bridge.get_rates(symbol, "H1", count=10)
        status = PASS if rates else WARN
        results.append(CheckResult(f"Rates ({symbol})", status, f"{len(rates)} H1 bars returned"))
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult(f"Rates ({symbol})", WARN, f"{type(exc).__name__}: {exc}"))

    # 8-9. Positions / orders (warnings only).
    try:
        positions = mt5_bridge.get_positions()
        results.append(CheckResult("Open positions", PASS, f"{len(positions)} open"))
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult("Open positions", WARN, f"{type(exc).__name__}: {exc}"))

    try:
        orders = mt5_bridge.get_orders()
        results.append(CheckResult("Pending orders", PASS, f"{len(orders)} pending"))
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult("Pending orders", WARN, f"{type(exc).__name__}: {exc}"))

    # 10-11. Directory configuration (informational).
    results.extend(_directory_checks())
    return results


def _directory_checks() -> list[CheckResult]:
    """Report the configured log and report directories. Informational (never FAIL)."""
    results: list[CheckResult] = []

    log_override = os.environ.get("MT5_MCP_LOG_SOURCE_DIR")
    if log_override:
        log_detail = f"MT5_MCP_LOG_SOURCE_DIR={log_override}"
    else:
        log_detail = "MT5_MCP_LOG_SOURCE_DIR unset; resolved from the terminal's data_path"
    results.append(CheckResult("Log directory config", PASS, log_detail))

    reports_override = os.environ.get("MT5_MCP_REPORTS_DIR")
    if reports_override:
        reports_detail = f"MT5_MCP_REPORTS_DIR={reports_override}"
    else:
        reports_detail = f"MT5_MCP_REPORTS_DIR unset; default '{DEFAULT_REPORTS_DIRNAME}/' under the working dir"
    results.append(CheckResult("Report directory config", PASS, reports_detail))
    return results


def format_table(results: list[CheckResult]) -> str:
    """Render the results as an aligned pass/fail table."""
    name_w = max((len(r.name) for r in results), default=4)
    lines = [
        "MetaTrader 5 readiness check (read-only; no orders are planned or sent)",
        "",
        f"{'CHECK'.ljust(name_w)}  STATUS  DETAIL",
        f"{'-' * name_w}  ------  ------",
    ]
    for r in results:
        lines.append(f"{r.name.ljust(name_w)}  {r.status.ljust(6)}  {r.detail}")
    return "\n".join(lines)


def exit_code(results: list[CheckResult]) -> int:
    """Non-zero only on clear readiness failures (FAIL); warnings/skips do not fail."""
    return 1 if any(r.status == FAIL for r in results) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only MetaTrader 5 readiness check (not an MCP tool).")
    parser.add_argument("--symbol", default="EURUSD", help="Symbol to probe for spec/tick/rates (default: EURUSD).")
    args = parser.parse_args(argv)

    results = run_checks(symbol=args.symbol)
    print(format_table(results))

    code = exit_code(results)
    print("")
    if code == 0:
        print("Result: READY (no hard failures). Reminder: this server only reads and plans; it never trades.")
    else:
        failed = ", ".join(r.name for r in results if r.status == FAIL)
        print(f"Result: NOT READY. Failed checks: {failed}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
