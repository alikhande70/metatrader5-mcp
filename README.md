# metatrader5-mcp

A local MCP (Model Context Protocol) server that connects Claude (or any MCP
client) to a running MetaTrader 5 terminal.

**Phase 1 scope only:** read-only market/account data, basic performance
analysis, and order *planning* (margin/profit calculations, order validation,
plan assembly). **No tool in this server sends, modifies, or cancels an order,
and live trading is always blocked.** This is a read/analysis/planning
foundation, not a trading bot.

## Requirements

- Windows, with a running MetaTrader 5 terminal (the `MetaTrader5` Python
  package only works on Windows, next to the terminal). On other platforms
  the server still runs and lists its tools, but every tool that touches MT5
  will raise a clear `MT5NotAvailableError`.
- Python 3.10+

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
| `MT5_MCP_REPORTS_DIR` | unset | Base directory for relative Strategy Tester report paths. |

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
tools and calls a couple of them.

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

**BLOCKED** (not implemented at all - no tool by these names exists, and the
router refuses them by name as a safety net): sending, modifying, or
cancelling any order; live trading in general.

See `docs/TOOLS.md` for full parameter reference, `docs/SAFETY.md` for how
the approval gate and risk guard work, and `docs/ARCHITECTURE.md` for the
module layout and request flow.

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
