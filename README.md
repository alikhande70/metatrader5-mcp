# metatrader5-mcp

A local MCP (Model Context Protocol) server that connects Claude (or any MCP
client) to a running MetaTrader 5 terminal.

A **user-directed bridge** between you, Claude, and MetaTrader 5. You can ask for
read-only market/account data, performance analysis, MQL5 development (read /
draft / diff / backup / approved file changes), compile and backtest preparation,
and report review. The design principle is **user authority broad, model autonomy
narrow**: every tool is governed by a `ToolPolicy` (permission level 0–5), the
model never auto-initiates a risky action, and file/runtime changes require
explicit human approval with a diff, a backup, a rollback point, and an audit
entry. **No tool sends, modifies, or cancels an order; live trading is never
implemented.** Chart/EA-runtime and live-account tools are declared in the policy
model but disabled by default. This is a tool-rich development bridge, not a
trading bot.

## Naming

The two names below differ intentionally:

- **Repository / project identity:** `metatrader5-mcp`
- **Installable package / command:** `mt5-mcp` (the Python import package is
  `mt5_mcp`, and `pip install -e .` also exposes an `mt5-mcp` console command)

## Requirements

- Windows, with a running MetaTrader 5 terminal (the `MetaTrader5` Python
  package only works on Windows, next to the terminal). On other platforms
  the server still runs and lists its tools, but every tool that touches MT5
  will raise a clear `MT5NotAvailableError`.
- Python 3.10+

> **New to this on Windows?** Follow `docs/QUICKSTART_WINDOWS.md` for a
> step-by-step setup, first tool calls, and a smoke-test checklist.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
```

## Configure

Copy `.env.example` to `.env` and adjust as needed. Nothing here is a secret
that gets committed - `.env` is gitignored, and the server never logs your
password.

```bash
cp .env.example .env
```

Key settings:

| Variable | Default | Purpose |
|---|---|---|
| `MT5_PATH`, `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` | unset | Optional explicit terminal/account to connect to. If unset, attaches to the terminal already running on the machine. |
| `MT5_MCP_APPROVAL_MODE` | `console` | `console` (type yes/no in the server's terminal) or `file` (approve via `approvals/approved_<id>.txt`). |
| `MT5_MCP_ENABLE_DEMO_TRADING` | `false` | Order-planning tools are disabled even on a demo account unless this is `true`. Real/contest accounts are **always** blocked regardless of this flag. |
| `MT5_MCP_LOG_DIR` | `logs` | Where `mt5_mcp.log` and `actions.log` are written. |
| `MT5_MCP_REPORTS_DIR` | `reports/` (under the runtime dir) | Directory that `read_strategy_report` / `tester_import_csv` are confined to (`.html`/`.htm`/`.csv`). Absolute paths and `..` traversal that escape it are rejected. |
| `MT5_MCP_WORKSPACE_DIR` | `workspace/` | MQL5 source root the file/code tools are confined to. Point at the terminal's `MQL5` data folder. |
| `MT5_MCP_BACKUPS_DIR` | `backups/` | Where file mutations write backups + rollback metadata, and where snapshots go. |
| `MT5_MCP_DRAFTS_DIR` | `drafts/` | Where `mql5_file_write_draft` writes drafts (never the real source). |
| `METAEDITOR_PATH` | unset | Full path to `metaeditor64.exe` for the compile tools (Windows only; off-Windows they return `UNSUPPORTED_IN_THIS_ENVIRONMENT`). |

## Run the server locally

```bash
python -m mt5_mcp.server
```

This starts the MCP server over stdio. Point any MCP client (Claude Desktop,
Claude Code, the `mcp` Python client, etc.) at this command. Example Claude
Desktop / Claude Code config:

```json
{
  "mcpServers": {
    "metatrader5": {
      "command": "python",
      "args": ["-m", "mt5_mcp.server"],
      "cwd": "/path/to/metatrader5-mcp"
    }
  }
}
```

See `examples/example_client.py` for a minimal standalone client that lists
tools and calls one tool per permission tier (read, analysis, and a
planning-only call that is never sent). `examples/claude_desktop_config.example.json`
and `examples/claude_code_config.example.json` show client wiring with the
venv's `python.exe` and an absolute `cwd`. `docs/EXAMPLES.md` walks through
usage by tool group.

Before pointing a client at the server, you can run the read-only readiness
helper to confirm your environment (it never plans or sends orders):

```bash
python scripts/mt5_readiness_check.py
```

## What's implemented

**SAFE_READ** (always allowed, logged, no approval needed):
`get_account_info`, `get_terminal_info`, `get_symbol_info`, `get_tick`,
`get_rates`, `get_positions`, `get_orders`, `get_history_deals`, `read_log`,
`read_strategy_report`.

**SAFE_ANALYSIS** (pure computation over data you already read, no approval
needed): `summarize_positions`, `analyze_drawdown`, `analyze_trade_history`,
`calculate_profit_risk_basic`.

**REQUIRES_APPROVAL** (order planning - margin/profit math and MT5's own
dry-run `order_check`; a human must approve every call, and the risk guard
still requires a demo account with `MT5_MCP_ENABLE_DEMO_TRADING=true`):
`calculate_margin`, `calculate_profit`, `check_order`, `prepare_order_plan`.

**Bridge tools** (governed by `ToolPolicy`; see `list_tool_policies`):
- *Workspace/code, Level 0/1* — workspace status & listing, `mql5_file_read`,
  `mql5_file_diff`, `mql5_file_write_draft`, `mql5_file_backup`, `mql5_code_review`,
  `mql5_code_generate_ea/indicator/script`, `mql5_code_fix_compile_error`. No
  approval; never mutate a real source file.
- *File mutations, Level 2* — `mql5_file_create/update/apply_patch/rename/delete/
  restore/revert_patch`, `workspace_restore_snapshot`. **Approval required**, with
  backup + diff + rollback id.
- *MetaEditor/Tester, Level 0/1 + gated Level 3* — `metaeditor_prepare_compile`,
  `metaeditor_parse_errors/warnings`, `metaeditor_generate_fix_plan`,
  `tester_prepare_signal_only_test`, `tester_import_csv`, `tester_review_results`,
  `tester_compare_runs`, `tester_generate_backtest_report`; plus the gated
  `metaeditor_run_compile` / `tester_run_backtest_if_supported` (Windows only).
- *Audit/introspection, Level 0* — `list_tool_policies`, `get_tool_policy`,
  `read_audit_log`.

**Declared but disabled (Level 4/5)** — `mt5_chart_*`, `mt5_ea_*`, `mt5_live_*`
are in the policy model but not registered as tools in this phase.

**BLOCKED** (not implemented at all - no tool by these names exists, and the
router refuses them by name as a safety net): sending, modifying, or
cancelling any order; live trading in general.

See `docs/TOOLS.md` for full parameter reference, `docs/EXAMPLES.md` for usage
examples by tool group, `docs/TROUBLESHOOTING.md` for a symptom → cause → fix
guide, `docs/SECURITY_MODEL.md` for the canonical safety model (how the approval
gate and risk guard work, and what is intentionally excluded), and
`docs/ARCHITECTURE.md` for the module layout and request flow. `docs/SAFETY.md`
is a short summary that points to `docs/SECURITY_MODEL.md`. See
`docs/RELEASE_CHECKLIST.md` for the maintainer checklist used before tagging a
release.

## Run the tests

```bash
pip install -e ".[dev]"
pytest
```

Tests run against a fake in-memory MT5 module (see `tests/conftest.py`), so
they pass on any platform without a real terminal.

## Known limitations (Phase 1)

- No order execution (`order_send`) - intentionally not implemented.
- No VPS/remote mode, no plugin system, no multi-strategy framework.
- `get_rates` only supports the "most recent N bars" mode
  (`copy_rates_from_pos`), not arbitrary date ranges.
- `read_strategy_report` uses a generic HTML table parser (label/value cell
  pairing); unusual report layouts may need raw row inspection.
- The file-based approval mode polls the filesystem; it is not push-based.
- No persistence/database - approvals and logs are plain files.
