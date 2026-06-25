# Security model (canonical)

This is the **source of truth** for what metatrader5-mcp is and is not allowed
to do. `docs/SAFETY.md` is a short compatibility summary that points here.

metatrader5-mcp is a **read / analysis / planning** server. It connects an MCP
client (Claude Desktop, Claude Code, etc.) to a locally running MetaTrader 5
terminal so the client can read market and account data, analyze trading
performance, and *plan* hypothetical orders. **It is not a trading bot.**

## The boundary in one sentence

No code path in this server sends, modifies, or cancels an order; live trading
is always blocked; and the order-*planning* tools only run after explicit human
approval, on a demo account, with demo planning explicitly enabled.

## Two independent, stacked safety layers

Both layers must allow an action before it runs. Either one alone is enough to
block it. Neither can be disabled by configuration.

### Layer 1 — Action classification + approval gate

Every tool name is classified exactly once in `permissions.py`:

| Category | Approval needed? | Examples |
|---|---|---|
| `SAFE_READ` | No | `get_account_info`, `get_rates`, `get_positions`, `read_log`, `read_strategy_report` |
| `SAFE_ANALYSIS` | No | `summarize_positions`, `analyze_drawdown`, `analyze_trade_history`, `calculate_profit_risk_basic` |
| `REQUIRES_APPROVAL` | Yes, every call | `calculate_margin`, `calculate_profit`, `check_order`, `prepare_order_plan` |
| `BLOCKED` | N/A — always refused | `send_order`, `place_order`, `modify_order`, `cancel_order`, `close_position`, … |

Every tool call is routed through `action_router.dispatch()`, which classifies
the action, logs the request, enforces approval when required, and only then
runs it.

- **Unknown action names default to `BLOCKED`** (fail-closed). There is no
  "default allow."
- The `BLOCKED` names are not implemented as tools — they exist in
  `permissions.py` only so the router refuses them on sight if anything ever
  tries to call them.

#### Approval modes (`MT5_MCP_APPROVAL_MODE`)

- **`console`** (default): the server prints the action and its parameters to
  stderr and waits for `yes`/`no` on stdin. If stdin is not a TTY, the request
  is **denied** — there is no way to silently approve.
- **`file`**: the server writes `approvals/pending_<action_id>.json` describing
  the request, then polls for `approvals/approved_<action_id>.txt` or
  `approvals/denied_<action_id>.txt`. If neither appears before the timeout
  (5 minutes by default), the request is **denied**.

**There is no auto-approval mode.** `get_approval_gate()` recognizes only
`"console"` and `"file"`; any other value raises `ValueError` rather than
falling back to "always approve."

### Layer 2 — Risk guard (live trading is never allowed)

`risk_guard.guard_order_tool(account_info, action_name)` runs at the start of
every `order_tools.*` function — `calculate_margin`, `calculate_profit`,
`check_order`, `prepare_order_plan` — independently of the approval gate:

- If the connected account's `trade_mode` is not demo (i.e. it is `real` or
  `contest`), the call is **always** refused. No environment variable or
  parameter overrides this.
- If the account is demo but `MT5_MCP_ENABLE_DEMO_TRADING` is not `true` (the
  default), the call is refused too. Order-planning tools are opt-in even in
  the safest case.

**Combined effect:** an order-planning tool runs only if **all** of the
following hold — a human approved that specific call, **and** the account is
demo, **and** the operator explicitly enabled demo planning. Even then, the
tool only computes margin/profit and runs MT5's dry-run `order_check`; it never
places an order.

## File-path confinement (SAFE_READ file tools)

`read_strategy_report` reads files from disk, so it must not become a way to
read arbitrary local files. Every requested path is resolved strictly inside
the reports directory (`MT5_MCP_REPORTS_DIR`, or the default `reports/` under
the runtime working directory):

- only `.html`/`.htm` files are accepted;
- the resolved real path must stay within the reports directory, so absolute
  paths pointing elsewhere and `..` traversal that escapes the directory are
  rejected with a `ReportPathError`.

(`read_log` similarly reads only MT5 log files from the terminal's log
directory or `MT5_MCP_LOG_SOURCE_DIR`.)

## Logging and auditability

- `logs/actions.log` — one JSON line per action request (with category and
  params), per approval/blocked decision, and per successful completion.
- `logs/mt5_mcp.log` — normal application/error logging (connection events,
  risk-guard warnings, etc.).

Neither log file is returned to the LLM as a tool result; they exist for the
human operator to audit.

## What is intentionally NOT implemented

These are excluded by design. They are absent from the codebase — not gated,
not stubbed — so there is no code path to bypass:

- ❌ Order execution / `order_send` of any kind.
- ❌ Modify / cancel / close / delete order tools.
- ❌ Live trading (real and contest accounts are always blocked from
  order-planning tools).
- ❌ VPS / remote execution mode.
- ❌ Auto-approval (no third approval mode exists).
- ❌ Any configuration that weakens `risk_guard`, `action_router`, or
  `permissions`.

Adding real order execution is an explicit, separate decision reserved for a
future phase with its own threat model and sign-off. It is **out of scope** for
the Phase 2 usability work.

## Related docs

- `docs/SAFETY.md` — short summary that points to this document.
- `docs/ARCHITECTURE.md` — module layout and request flow.
- `docs/TOOLS.md` — per-tool parameter reference.
- `docs/QUICKSTART_WINDOWS.md` — Windows setup and smoke-test checklist.
