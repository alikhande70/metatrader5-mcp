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

from . import (
    analysis_tools,
    audit_tools,
    code_gen,
    log_reader,
    metaeditor_adapter,
    mql5_files,
    mt5_bridge,
    order_tools,
    report_reader,
    tester_adapter,
    workspace_tools,
)
from .action_router import dispatch
from .approval_gate import get_approval_gate
from .utils import get_logger

logger = get_logger(__name__)

mcp = FastMCP(
    "metatrader5-mcp",
    instructions=(
        "User-directed bridge between Claude and MetaTrader 5. The owner can request "
        "reads, analysis, MQL5 development (read/draft/diff/backup/approved file changes), "
        "compile/backtest preparation, and report review. Every tool is governed by a "
        "ToolPolicy (see list_tool_policies): the model never auto-initiates a risky "
        "action - file changes and runtime actions require explicit human approval, with "
        "backup, diff, and an audit trail. No tool sends, modifies, or cancels an order; "
        "live trading is never implemented. Chart/EA-runtime and live-account tools are "
        "declared in the policy model but disabled by default."
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


# --- INTROSPECTION / AUDIT (Level 0) -----------------------------------------


@mcp.tool()
def list_tool_policies() -> dict:
    """List every tool with its permission level, risk, and gating flags (the capability model)."""
    return _run("list_tool_policies", audit_tools.list_tool_policies, {})


@mcp.tool()
def get_tool_policy(name: str) -> dict:
    """Return the full ToolPolicy (all capability fields) for a single tool name."""
    return _run("get_tool_policy", audit_tools.get_tool_policy, {"name": name})


@mcp.tool()
def read_audit_log(lines: int = 100) -> dict:
    """Read the tail of the bridge's JSONL action/audit log (logs/actions.log)."""
    return _run("read_audit_log", audit_tools.read_audit_log, {"lines": lines})


# --- WORKSPACE (Level 0 reads; Level 2 restore) ------------------------------


@mcp.tool()
def workspace_show_status() -> dict:
    """Summarise the MQL5 workspace: root, existence, and source counts per kind."""
    return _run("workspace_show_status", workspace_tools.show_status, {})


@mcp.tool()
def workspace_detect_data_folder() -> dict:
    """Report the configured MQL5 workspace/Data Folder (auto-detect needs Windows + MT5)."""
    return _run("workspace_detect_data_folder", workspace_tools.detect_data_folder, {})


@mcp.tool()
def workspace_list_experts() -> dict:
    """List Expert Advisor source files in the workspace."""
    return _run("workspace_list_experts", workspace_tools.list_sources, {"kind": "experts"})


@mcp.tool()
def workspace_list_indicators() -> dict:
    """List indicator source files in the workspace."""
    return _run("workspace_list_indicators", workspace_tools.list_sources, {"kind": "indicators"})


@mcp.tool()
def workspace_list_scripts() -> dict:
    """List script source files in the workspace."""
    return _run("workspace_list_scripts", workspace_tools.list_sources, {"kind": "scripts"})


@mcp.tool()
def workspace_list_includes() -> dict:
    """List include (.mqh) files in the workspace."""
    return _run("workspace_list_includes", workspace_tools.list_sources, {"kind": "includes"})


@mcp.tool()
def workspace_snapshot(label: str | None = None) -> dict:
    """Create a zip snapshot of the workspace under the backups directory (safe; does not modify sources)."""
    return _run("workspace_snapshot", workspace_tools.snapshot, {"label": label})


@mcp.tool()
def workspace_restore_snapshot(archive: str, overwrite: bool = True) -> dict:
    """Restore a workspace snapshot zip into the workspace. Mutating; requires approval."""
    return _run(
        "workspace_restore_snapshot",
        workspace_tools.restore_snapshot,
        {"archive": archive, "overwrite": overwrite},
        description=f"Restore workspace snapshot {archive} (overwrite={overwrite})",
    )


# --- MQL5 FILES: read / diff / draft (Level 0/1) -----------------------------


@mcp.tool()
def mql5_file_read(path: str) -> dict:
    """Read a workspace MQL5 source file (confined to the workspace root)."""
    return _run("mql5_file_read", mql5_files.read, {"path": path})


@mcp.tool()
def mql5_file_diff(path: str, new_content: str) -> dict:
    """Show a unified diff between the current file and proposed `new_content` (no write)."""
    return _run("mql5_file_diff", mql5_files.diff, {"path": path, "new_content": new_content})


@mcp.tool()
def mql5_file_write_draft(path: str, content: str) -> dict:
    """Write proposed content to the drafts directory (never the real source) and show the diff."""
    return _run("mql5_file_write_draft", mql5_files.write_draft, {"path": path, "content": content})


@mcp.tool()
def mql5_file_backup(path: str) -> dict:
    """Copy a source file into the backups directory (safe; does not modify the source)."""
    return _run("mql5_file_backup", mql5_files.backup, {"path": path})


@mcp.tool()
def mql5_code_review(path: str) -> dict:
    """Run lightweight static review heuristics over a workspace MQL5 file (read-only)."""
    return _run("mql5_code_review", code_gen.code_review, {"path": path})


@mcp.tool()
def mql5_code_generate_ea(name: str, magic: int = 0, author: str = "mt5-mcp") -> dict:
    """Generate an Expert Advisor draft (returns code; does not write to the workspace)."""
    return _run("mql5_code_generate_ea", code_gen.generate_ea, {"name": name, "magic": magic, "author": author})


@mcp.tool()
def mql5_code_generate_indicator(name: str, author: str = "mt5-mcp") -> dict:
    """Generate an indicator draft (returns code; does not write to the workspace)."""
    return _run("mql5_code_generate_indicator", code_gen.generate_indicator, {"name": name, "author": author})


@mcp.tool()
def mql5_code_generate_script(name: str, author: str = "mt5-mcp") -> dict:
    """Generate a script draft (returns code; does not write to the workspace)."""
    return _run("mql5_code_generate_script", code_gen.generate_script, {"name": name, "author": author})


@mcp.tool()
def mql5_code_fix_compile_error(errors: list[dict], source_path: str | None = None) -> dict:
    """Turn parsed compiler errors into a human-reviewable fix plan (no code change)."""
    return _run(
        "mql5_code_fix_compile_error",
        code_gen.fix_compile_error,
        {"errors": errors, "source_path": source_path},
    )


# --- MQL5 FILES: mutations (Level 2: approval + backup + diff + rollback) -----


@mcp.tool()
def mql5_file_create(path: str, content: str) -> dict:
    """Create a new workspace file. Requires approval; records a rollback point."""
    return _run("mql5_file_create", mql5_files.create, {"path": path, "content": content},
                description=f"Create file {path}")


@mcp.tool()
def mql5_file_update(path: str, content: str) -> dict:
    """Overwrite a workspace file with new content. Requires approval; backs up + records rollback."""
    return _run("mql5_file_update", mql5_files.update, {"path": path, "content": content},
                description=f"Update file {path}")


@mcp.tool()
def mql5_file_apply_patch(path: str, find: str, replace: str, count: int = 0) -> dict:
    """Apply a find/replace patch to a file. Requires approval; backs up + records rollback."""
    return _run("mql5_file_apply_patch", mql5_files.apply_patch,
                {"path": path, "find": find, "replace": replace, "count": count},
                description=f"Apply patch to {path}")


@mcp.tool()
def mql5_file_revert_patch(rollback_id: str) -> dict:
    """Undo a previous mutation using its rollback id. Requires approval."""
    return _run("mql5_file_revert_patch", mql5_files.revert_patch, {"rollback_id": rollback_id},
                description=f"Revert change {rollback_id}")


@mcp.tool()
def mql5_file_restore(path: str, backup_path: str) -> dict:
    """Restore a file from a backup. Requires approval; backs up the current state first."""
    return _run("mql5_file_restore", mql5_files.restore, {"path": path, "backup_path": backup_path},
                description=f"Restore {path} from {backup_path}")


@mcp.tool()
def mql5_file_rename(path: str, new_path: str) -> dict:
    """Rename/move a workspace file. Requires approval; records a rollback point."""
    return _run("mql5_file_rename", mql5_files.rename, {"path": path, "new_path": new_path},
                description=f"Rename {path} -> {new_path}")


@mcp.tool()
def mql5_file_delete(path: str) -> dict:
    """Delete a workspace file. Requires approval; backs up content so it can be restored."""
    return _run("mql5_file_delete", mql5_files.delete, {"path": path}, description=f"Delete file {path}")


# --- METAEDITOR ADAPTERS (Level 0/1 prepare+parse; Level 3 run) ---------------


@mcp.tool()
def metaeditor_detect_path() -> dict:
    """Locate metaeditor64.exe via METAEDITOR_PATH or common install dirs (Windows only)."""
    return _run("metaeditor_detect_path", metaeditor_adapter.detect_path, {})


@mcp.tool()
def metaeditor_prepare_compile(source_path: str, include_path: str | None = None) -> dict:
    """Build the metaeditor64.exe /compile command line for a source file (no execution)."""
    return _run("metaeditor_prepare_compile", metaeditor_adapter.prepare_compile,
                {"source_path": source_path, "include_path": include_path})


@mcp.tool()
def metaeditor_run_compile(source_path: str, include_path: str | None = None, timeout_s: int = 120) -> dict:
    """Run MetaEditor's compiler (Windows + MetaEditor only; else returns a gated payload). Requires approval."""
    return _run("metaeditor_run_compile", metaeditor_adapter.run_compile,
                {"source_path": source_path, "include_path": include_path, "timeout_s": timeout_s},
                description=f"Compile {source_path} with MetaEditor")


@mcp.tool()
def metaeditor_read_compile_log(path: str) -> dict:
    """Read a MetaEditor compile .log file from inside the workspace."""
    return _run("metaeditor_read_compile_log", metaeditor_adapter.read_compile_log, {"path": path})


@mcp.tool()
def metaeditor_parse_errors(log_text: str) -> dict:
    """Parse `error` lines out of MetaEditor compile-log text."""
    return _run("metaeditor_parse_errors", metaeditor_adapter.parse_errors, {"log_text": log_text})


@mcp.tool()
def metaeditor_parse_warnings(log_text: str) -> dict:
    """Parse `warning` lines out of MetaEditor compile-log text."""
    return _run("metaeditor_parse_warnings", metaeditor_adapter.parse_warnings, {"log_text": log_text})


@mcp.tool()
def metaeditor_generate_fix_plan(log_text: str, source_path: str | None = None) -> dict:
    """Parse compile errors and produce a human-reviewable fix plan (no code change)."""
    return _run("metaeditor_generate_fix_plan", metaeditor_adapter.generate_fix_plan,
                {"log_text": log_text, "source_path": source_path})


# --- STRATEGY TESTER ADAPTERS (Level 0/1 prepare+import+review; Level 3 run) --


@mcp.tool()
def tester_prepare_signal_only_test(
    expert: str,
    symbol: str,
    timeframe: str = "H1",
    date_from: str = "2023.01.01",
    date_to: str = "2023.12.31",
    deposit: float = 10000.0,
    model: int = 1,
) -> dict:
    """Build a Strategy Tester .ini config draft for a non-live test (no execution)."""
    return _run("tester_prepare_signal_only_test", tester_adapter.prepare_signal_only_test,
                {"expert": expert, "symbol": symbol, "timeframe": timeframe, "date_from": date_from,
                 "date_to": date_to, "deposit": deposit, "model": model})


@mcp.tool()
def tester_run_backtest_if_supported(config_ini: str | None = None) -> dict:
    """Run a backtest if a Windows MT5 runtime is available; otherwise return a gated payload. Requires approval."""
    return _run("tester_run_backtest_if_supported", tester_adapter.run_backtest_if_supported,
                {"config_ini": config_ini}, description="Run Strategy Tester backtest")


@mcp.tool()
def tester_import_csv(path: str) -> dict:
    """Import an exported Strategy Tester CSV (confined to the reports directory)."""
    return _run("tester_import_csv", tester_adapter.import_csv, {"path": path})


@mcp.tool()
def tester_review_results(summary: dict) -> dict:
    """Normalise and flag a parsed Strategy Tester summary (from read_strategy_report)."""
    return _run("tester_review_results", tester_adapter.review_results, {"summary": summary})


@mcp.tool()
def tester_compare_runs(runs: list[dict]) -> dict:
    """Compare several reviewed/summary runs and pick the best by key metrics."""
    return _run("tester_compare_runs", tester_adapter.compare_runs, {"runs": runs})


@mcp.tool()
def tester_generate_backtest_report(review: dict, title: str = "Backtest Review") -> dict:
    """Render a reviewed result into a concise Markdown report (draft)."""
    return _run("tester_generate_backtest_report", tester_adapter.generate_backtest_report,
                {"review": review, "title": title})


def main() -> None:
    logger.info("Starting metatrader5-mcp server (user-directed bridge: read/analysis/dev/compile-prep; no execution).")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
