# Safety model

Phase 1 has two independent, stacked safety mechanisms. Both must allow an
action before it runs; either one alone is enough to block it.

## 1. Action classification + approval gate

Every tool name is classified exactly once in `permissions.py`:

| Category | Approval needed? | Examples |
|---|---|---|
| `SAFE_READ` | No | `get_account_info`, `get_rates`, `get_positions` |
| `SAFE_ANALYSIS` | No | `summarize_positions`, `analyze_drawdown` |
| `REQUIRES_APPROVAL` | Yes, every call | `calculate_margin`, `check_order`, `prepare_order_plan` |
| `BLOCKED` | N/A - always refused | `send_order`, `place_order`, ... (none of these are implemented; the names exist only so the router refuses them on sight) |

**Unknown action names default to `BLOCKED`.** There is no "default allow."

### Approval modes (`MT5_MCP_APPROVAL_MODE`)

- **`console`** (default): the server process prints the action, its
  parameters, and waits for `yes`/`no` on stdin. If stdin isn't a TTY (e.g.
  the server is running as a background service), the request is denied -
  there's no way to silently approve.
- **`file`**: the server writes `approvals/pending_<action_id>.json`
  describing the request, then polls for either
  `approvals/approved_<action_id>.txt` or `approvals/denied_<action_id>.txt`
  to appear (any file content works - the filename is what matters). If
  neither appears within the timeout (5 minutes by default), the request is
  denied. A human (or a script acting on a human's explicit instruction)
  must create that file.

**There is no auto-approval mode.** `get_approval_gate()` only recognizes
`"console"` and `"file"`; any other value raises `ValueError` rather than
falling back to an "always approve" behavior.

## 2. Risk guard (live trading is never allowed)

`risk_guard.guard_order_tool(account_info, action_name)` runs at the start of
every `order_tools.*` function - `calculate_margin`, `calculate_profit`,
`check_order`, `prepare_order_plan` - independently of the approval gate:

- If the connected account's `trade_mode` is not `ACCOUNT_TRADE_MODE_DEMO`
  (i.e. it's `real` or `contest`), the call is **always** refused. There is
  no environment variable or parameter that overrides this.
- If the account is demo but `MT5_MCP_ENABLE_DEMO_TRADING` is not `true`
  (the default), the call is refused too. Order-planning tools are opt-in
  even in the safest case.

Combined effect: an order-planning tool only runs if **both** a human
approved that specific call **and** the connected account is demo **and**
the operator explicitly enabled demo trading.

## What's still missing on purpose

`order_send` (and any modify/cancel equivalent) is not implemented anywhere
in this codebase - not gated, not stubbed, just absent. There is nothing to
bypass because there is no code path that would place a real order. Adding
real execution is an explicit, separate decision for a later phase.

## Logging

`logs/actions.log` gets one JSON line per: action request (with category and
params), approval/blocked decision, and successful completion. `logs/mt5_mcp.log`
gets normal application/error logging (connection events, risk guard
warnings, etc). Neither file is given to the LLM as a tool result - they're
for the human operator to audit.
