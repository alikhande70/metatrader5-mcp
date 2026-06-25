# Troubleshooting

Symptom → likely cause → fix, for the most common setup and runtime problems.
Most issues are environment-related (wrong Python, no terminal) rather than
bugs in the server.

> Reminder: this server is read / analysis / planning only. It never sends,
> modifies, or cancels orders, and live trading is always blocked. If a
> `REQUIRES_APPROVAL` planning call is refused, that is the risk guard doing its
> job — see [risk_guard refusal](#risk_guard-refuses-a-planning-call) below.

A quick first step for most of these: run the read-only readiness helper, which
prints a pass/fail table for the whole environment:

```bat
python scripts\mt5_readiness_check.py
```

---

## Wrong Python / not using the venv

**Symptom:** `ModuleNotFoundError: No module named 'mt5_mcp'` (or `mcp`,
`pytest`), or the MCP client fails to launch the server.

**Likely cause:** you are running a different Python than the one where the
package was installed (system Python instead of the project `.venv`).

**Fix:** activate the venv and reinstall, then use that interpreter everywhere
— including in your MCP client config:

```bat
.venv\Scripts\activate
pip install -e ".[dev]"
python -c "import mt5_mcp; print('ok')"
```

In `claude_desktop_config.example.json` / `claude_code_config.example.json`, set
`command` to the venv's `python.exe` (e.g.
`C:\path\to\metatrader5-mcp\.venv\Scripts\python.exe`), not a bare `python`.

---

## MetaTrader5 package missing

**Symptom:** `MT5NotAvailableError: The MetaTrader5 package is not installed ...`
on Windows.

**Likely cause:** dependencies were not installed into the active environment.

**Fix:**

```bat
pip install -e ".[dev]"
```

On Windows this also installs the `MetaTrader5` wheel (it is declared with a
`sys_platform == 'win32'` marker). Restart the server afterwards.

---

## Non-Windows environment

**Symptom:** `MT5NotAvailableError: ... not available on this platform ('linux'/'darwin') ...`

**Likely cause:** the `MetaTrader5` package only works on Windows, next to a
running terminal. This is expected, not a bug.

**Fix:** run the server (and the readiness check) on **Windows** with the MT5
terminal installed. On other platforms the server still starts and lists its
tools, and the test suite still passes (it uses a fake MT5), but any tool that
touches MT5 will raise this error.

---

## MT5 terminal not running

**Symptom:** `MT5ConnectionError: MetaTrader5.initialize() failed ...` listing
"the MT5 terminal is not running" among the likely causes.

**Likely cause:** no MetaTrader 5 terminal is open, so there is nothing to
attach to.

**Fix:** launch the MetaTrader 5 terminal, log into your **demo** account, and
leave it running. Then retry.

---

## Wrong MT5_PATH

**Symptom:** `MT5ConnectionError` with `path=...` pointing at the wrong place,
or initialize launching the wrong/secondary terminal.

**Likely cause:** `MT5_PATH` is set to an incorrect `terminal64.exe` location.

**Fix:** either unset `MT5_PATH` (the server then attaches to the
already-running terminal) or point it at the correct `terminal64.exe`:

```bat
set MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

---

## Terminal not logged in

**Symptom:** `MT5ConnectionError` mentioning "running but not logged in", or
`get_account_info` failing right after a successful connect.

**Likely cause:** the terminal is open but not logged into an account, or
`MT5_LOGIN`/`MT5_SERVER`/`MT5_PASSWORD` are wrong.

**Fix:** log into a **demo** account inside the terminal. If you pass credentials
via env vars, double-check `MT5_LOGIN`, `MT5_SERVER`, and `MT5_PASSWORD`. The
server never logs your password.

---

## Symbol not found

**Symptom:** `MT5RequestError: symbol_info(XYZ) failed ...` mentioning that
`symbol_select` was attempted.

**Likely cause:** the symbol does not exist on your broker/server, or it is not
visible in Market Watch.

**Fix:** open Market Watch (Ctrl+M) in the terminal, right-click → **Show All**
(or add the symbol), and confirm the exact broker spelling (e.g. `EURUSD` vs
`EURUSD.m`). Then retry, e.g.:

```bat
python scripts\mt5_readiness_check.py --symbol EURUSD
```

---

## Report not found

**Symptom:** `FileNotFoundError: Strategy Tester report not found: ...`, often
with a list of available reports.

**Likely cause:** the file is not inside the configured reports directory, or
the name/extension is wrong (only `.html`/`.htm` are allowed).

**Fix:** put the exported report under `MT5_MCP_REPORTS_DIR` (default `reports/`
under the working directory) and pass a path **relative to that directory**.
Absolute paths and `..` traversal that escape it are rejected by design. The
error message lists the resolved base directory and the reports it can see.

---

## Log not found

**Symptom:** `FileNotFoundError: Log file not found: ...`, often listing
available dates.

**Likely cause:** there is no log for the requested date, or the wrong `kind`
was requested (`terminal` vs `experts`), or the log directory is misconfigured.

**Fix:** call `read_log()` with no date for today, or pass a date that exists
(the error lists available dates). Use `kind="experts"` for Expert Advisor logs.
If you override the location, set `MT5_MCP_LOG_SOURCE_DIR`; otherwise the
directory is resolved from the terminal's `data_path`.

---

## Approval timeout

**Symptom:** a `REQUIRES_APPROVAL` call hangs and then reports that approval
timed out / was not granted.

**Likely cause:** no one answered the approval prompt in time.

**Fix:**

- **Console mode** (`MT5_MCP_APPROVAL_MODE=console`): answer the `y/n` prompt in
  the terminal where the server is running.
- **File mode** (`MT5_MCP_APPROVAL_MODE=file`): create the
  `approvals/approved_<id>.txt` file referenced by the pending request before
  the timeout.

Approval is intentional friction around planning calls — there is no
auto-approval, and that is by design.

---

## risk_guard refuses a planning call

**Symptom:** `RiskGuardError: '<tool>' is blocked: ... trade_mode is 'real'/'contest'/...`
or a message about `MT5_MCP_ENABLE_DEMO_TRADING`.

**Likely cause:** this is **not** a bug — the risk guard blocks order-planning
tools on anything but an explicitly enabled demo account.

**Fix:**

- **Real or contest account:** there is no override. Order-planning tools are
  always blocked. Use a **demo** account.
- **Demo account:** set `MT5_MCP_ENABLE_DEMO_TRADING=true` to allow *planning*
  (still never execution) on demo, then approve the call.

---

## stdio MCP startup failure

**Symptom:** the MCP client shows the server as failed/disconnected, or you see
no tools.

**Likely cause:** the client cannot launch `python -m mt5_mcp.server` (wrong
interpreter, wrong `cwd`, or an import error at startup).

**Fix:**

1. Run the server standalone first to surface errors directly:

   ```bat
   python -m mt5_mcp.server
   ```

2. In the client config, use the **venv's** `python.exe` for `command` and an
   **absolute** path for `cwd` (see the example configs).
3. Confirm `pip install -e .` succeeded in that same venv.

---

If none of the above resolves it, the readiness helper output
(`python scripts\mt5_readiness_check.py`) plus the first lines of any error are
the most useful things to capture.
