# Quickstart — Windows + MetaTrader 5

This walks you from a fresh clone to your first successful tool call against a
**real, running MetaTrader 5 terminal** on Windows.

> **Safety reminder.** This server is read / analysis / planning only. It never
> sends, modifies, or cancels orders, and live trading is always blocked. See
> [`SECURITY_MODEL.md`](SECURITY_MODEL.md) for the full model. Use a **demo**
> account for everything below.

## Requirements

- Windows (the `MetaTrader5` Python package only works on Windows, next to the
  terminal).
- Python 3.10 or 3.11.
- MetaTrader 5 terminal installed and logged into a **demo** account.

## 1. Clone and create a virtual environment

```bat
git clone https://github.com/alikhande70/metatrader5-mcp.git
cd metatrader5-mcp
py -3.11 -m venv .venv
.venv\Scripts\activate
python --version
```

`python --version` should report 3.10.x or 3.11.x. Make sure the prompt shows
the `(.venv)` prefix before continuing — later steps must use this interpreter.

## 2. Install

```bat
pip install -e ".[dev]"
```

On Windows this also installs the `MetaTrader5` package (it is declared with a
`sys_platform == 'win32'` marker, so it is only pulled in here, not on Linux
CI).

## 3. Run the test suite (no terminal needed)

```bat
pytest
```

These tests run against a fake in-memory MT5 module, so they pass without a
terminal and confirm your install is healthy.

## 4. Start MetaTrader 5

1. Launch the MetaTrader 5 terminal and log into a **demo** account.
2. Open Market Watch (Ctrl+M) and make sure your test symbol (e.g. `EURUSD`)
   is visible.
3. Leave the terminal running.

## 5. Configure (optional)

Copy `.env.example` to `.env` and adjust if needed. With no `.env`, the server
attaches to the already-running terminal and uses safe defaults (console
approval, demo planning disabled, `logs/` and `reports/` under the working
directory).

```bat
copy .env.example .env
```

Never commit `.env` — it is gitignored and may contain account details.

## 6. Check readiness (read-only)

Run the read-only readiness helper. It performs only SAFE_READ-style checks
(availability, connection, account/terminal info, a symbol, a tick, rates,
positions, orders, log + report directory configuration) and prints a pass/fail
table. **It does not place orders, does not call `order_send`, and does not
require approval** (it never calls a REQUIRES_APPROVAL tool).

```bat
python scripts\mt5_readiness_check.py
```

It prints a pass/fail table and exits non-zero only on clear readiness
failures. You can probe a specific symbol with `--symbol GBPUSD`. For the
manual, tool-by-tool acceptance checklist, see the next section.

## 7. Run the MCP server

```bat
python -m mt5_mcp.server
```

This starts the server over stdio. Point your MCP client at this command (see
[Wiring an MCP client](#wiring-an-mcp-client) below). To exit, press Ctrl+C.

---

## Windows smoke-test checklist

This is the manual acceptance checklist for a real Windows + MT5 demo terminal.
Run it before tagging a release. Fill in the **Result** and **Notes** columns
and paste the completed table into the release notes.

> Until a maintainer provides the **completed** table below, the Windows smoke
> test is considered **NOT yet passed**.

### Environment prep

| # | Step | Command | Expected | Result (pass/fail) | Notes |
|---|------|---------|----------|--------------------|-------|
| 1 | Fresh clone | `git clone … && cd metatrader5-mcp` | Clean working tree on the release branch | | |
| 2 | Python venv | `py -3.11 -m venv .venv` + `.venv\Scripts\activate` | `python --version` is 3.10.x or 3.11.x | | |
| 3 | Install | `pip install -e ".[dev]"` | `MetaTrader5` wheel installs; no errors | | |
| 4 | pytest | `pytest` | All tests pass (fake MT5) | | |
| 5 | MT5 running | Launch terminal, log into **demo**, show `EURUSD` in Market Watch | Terminal connected to demo account | | |

### SAFE_READ tools against the live terminal

| # | Step | Tool / call | Expected | Result (pass/fail) | Notes |
|---|------|-------------|----------|--------------------|-------|
| 6 | Attach to existing terminal | readiness check / server start | Attaches to running terminal (no path needed) | | |
| 7 | Account info | `get_account_info` | Real login/balance/equity; **`trade_mode` = demo** | | |
| 8 | Terminal info | `get_terminal_info` | `connected: true`, valid `data_path` | | |
| 9 | Symbol info | `get_symbol_info("EURUSD")` | digits/point/contract size returned | | |
| 10 | Tick | `get_tick("EURUSD")` | Live bid/ask, recent timestamp | | |
| 11 | Rates | `get_rates("EURUSD","H1",count=100)` | 100 OHLCV bars, chronological | | |
| 12 | Positions | `get_positions()` | Empty or well-formed demo positions | | |
| 13 | Orders | `get_orders()` | Empty or well-formed pending orders | | |
| 14 | History deals | `get_history_deals(date_from,date_to)` | Deals for a known range; known trade present | | |
| 15 | Read log | `read_log()` | Tail of today's terminal log; decodes correctly (UTF-16/UTF-8) | | |
| 16 | Strategy report | `read_strategy_report("<file>.htm")` | Summary keys parse; path stays inside `MT5_MCP_REPORTS_DIR` | | |

**Exit criteria:** steps 1–16 all pass on a real Windows + MT5 demo install. A
release is not considered Windows-validated until this table is completed and
attached.

---

## Wiring an MCP client

Point your MCP client at `python -m mt5_mcp.server`, using the **venv's**
Python and an **absolute** `cwd`. Full client details and Windows path gotchas
will be expanded in the Phase 2 examples PR; the minimal form is:

```json
{
  "mcpServers": {
    "metatrader5": {
      "command": "C:\\path\\to\\metatrader5-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mt5_mcp.server"],
      "cwd": "C:\\path\\to\\metatrader5-mcp"
    }
  }
}
```

See also [`examples/claude_desktop_config.example.json`](../examples/claude_desktop_config.example.json),
[`examples/claude_code_config.example.json`](../examples/claude_code_config.example.json),
and [`examples/example_client.py`](../examples/example_client.py). For usage
examples by tool group, see [`EXAMPLES.md`](EXAMPLES.md).

## If something goes wrong

See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for a full symptom → cause → fix
guide. Quick pointers:

- **`MT5NotAvailableError`** — you are not on Windows, or the `MetaTrader5`
  package did not install. Confirm the venv and `pip install -e ".[dev]"`.
- **Connection/initialize failures** — terminal not running, not logged in, or
  AutoTrading disabled; check `MT5_PATH`/`MT5_LOGIN`/`MT5_SERVER` if set.
- **Client won't start the server** — run `python -m mt5_mcp.server` standalone
  first to surface import/path errors; ensure the client uses the venv Python
  and an absolute `cwd`.
