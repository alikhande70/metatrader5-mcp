# Architecture

```
src/mt5_mcp/
  server.py          FastMCP tool registration. Every tool body calls action_router.dispatch().
  policy.py          Canonical capability manifest: ToolPolicy + PermissionLevel(0-5) + RiskLevel.
  permissions.py     Derives SAFE_READ | SAFE_ANALYSIS | REQUIRES_APPROVAL | BLOCKED from policy.py.
  action_router.py   Single choke point: classify -> gate (approve/double) -> audit -> execute.
  approval_gate.py   Console and file-based human approval (single + double). No auto-approval mode.
  risk_guard.py       Hard block on live/contest accounts; demo trading is opt-in (default off).
  paths.py            Shared filesystem-confinement helper (resolve_within).
  mt5_bridge.py       Only module that imports `MetaTrader5`. Read wrappers + calc/check wrappers.
  analysis_tools.py   Pure functions over plain dicts (no MT5 connection).
  order_tools.py      Order planning: margin/profit calc, order_check, prepare_order_plan. Never order_send.
  log_reader.py        Reads MT5 terminal/expert .log files.
  report_reader.py    Parses Strategy Tester HTML reports.
  workspace_tools.py  MQL5 workspace config + listing + snapshot/restore.
  mql5_files.py       MQL5 file read/diff/draft + approval-gated mutations (backup+diff+rollback).
  code_gen.py         MQL5 code drafting, static review, compile-error fix plans.
  metaeditor_adapter.py  Prepare/parse compile (pure) + gated run_compile (Windows-only).
  tester_adapter.py   Strategy Tester config drafts, CSV import, run review/compare (gated run).
  audit_tools.py      Policy introspection (list/get) + read_audit_log.
  utils.py            Logging setup, JSON action-log writer, MT5 struct -> dict conversion.
```

`policy.py` is the single source of truth. `ToolPolicy` records two independent
flags — `user_can_request` (always true) and `model_can_initiate` (false for
risky tools) — plus per-tool gating/requirement flags and forbidden-capability
flags (`can_send_order`, …) that import-time invariants force to stay False.
Levels 4/5 (chart/EA runtime, live) are declared but disabled by default and not
registered as MCP tools in this phase.

## Request flow

Every tool in `server.py` looks like:

```python
@mcp.tool()
def get_account_info() -> dict:
    return _run("get_account_info", mt5_bridge.get_account_info, {})
```

`_run` calls `action_router.dispatch(action_name, executor, params, approval_gate, description)`,
which always does, in order:

1. **Classify** - `permissions.classify(action_name)`. Unknown names default to
   `BLOCKED` (fail closed), never to a safe category.
2. **Log the request** - one JSON line in `logs/actions.log` with the action,
   category, and params, before anything else happens.
3. **Block** - if the category is `BLOCKED`, raise immediately. The executor
   is never called.
4. **Approve** - if the category is `REQUIRES_APPROVAL`, call
   `approval_gate.request_approval(...)` and log the decision
   (`approved`/`denied`). If denied, raise; the executor is never called.
5. **Execute** - call the actual function (`mt5_bridge.*`, `analysis_tools.*`,
   `order_tools.*`, `log_reader.*`, `report_reader.*`).
6. **Log completion**.

`order_tools.*` functions add a second, independent layer underneath this:
each one re-fetches `account_info` and calls `risk_guard.guard_order_tool()`
before doing anything else. This means even if a human approves an
order-planning call, it still will not run against a real/contest account,
and will not run against a demo account unless
`MT5_MCP_ENABLE_DEMO_TRADING=true`. Approval and risk guard are deliberately
two separate, non-bypassable checks.

## Why `mt5_bridge.py` is the only place that imports `MetaTrader5`

The `MetaTrader5` package only works on Windows, next to a running terminal.
Importing it eagerly at module load time would break this package on every
other platform (including CI). `mt5_bridge._get_mt5()` imports it lazily on
first use and raises a clear `MT5NotAvailableError` if it can't be imported.
Tests inject a fake module by setting `mt5_bridge._mt5_module` directly
(see `tests/conftest.py::FakeMT5`), bypassing the import entirely.

## Data shapes

MT5 API calls return namedtuple-like structs (`account_info()`,
`symbol_info()`, ...) or tuples of them (`positions_get()`, ...).
`utils.mt5_struct_to_dict()` recursively converts these into plain
dicts/lists so every tool returns JSON-serializable data to the MCP client.
`copy_rates_from_pos()` returns a numpy structured array instead, which
`mt5_bridge._rates_to_list()` converts the same way without requiring numpy
as a direct dependency of this package (it rides along as MetaTrader5's own
dependency on Windows).
