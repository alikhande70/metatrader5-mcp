# Safety model (summary)

> **This is a short summary. The canonical safety document is
> [`SECURITY_MODEL.md`](SECURITY_MODEL.md) — read it for the full, authoritative
> details.** This page is kept so existing links to `SAFETY.md` still work.

metatrader5-mcp is a **read / analysis / planning** server, not a trading bot.

**Two stacked safety layers, both required, neither disableable:**

1. **Action classification + approval gate** — every tool is classified in
   `permissions.py` as `SAFE_READ`, `SAFE_ANALYSIS`, `REQUIRES_APPROVAL`, or
   `BLOCKED`, and routed through `action_router.dispatch()`. Unknown names
   default to `BLOCKED` (fail-closed). `REQUIRES_APPROVAL` tools need explicit
   human approval (`console` or `file` mode). **There is no auto-approval
   mode.**
2. **Risk guard** — order-planning tools are always refused on real/contest
   accounts (no override) and refused on demo unless
   `MT5_MCP_ENABLE_DEMO_TRADING=true`.

**File-path confinement:** `read_strategy_report` only reads `.html`/`.htm`
files inside `MT5_MCP_REPORTS_DIR` (default `reports/`); absolute paths and
`..` traversal that escape it are rejected.

**Not implemented on purpose (absent, not just gated):** order execution,
`order_send`, modify/cancel/close/delete order tools, live trading, VPS/remote
mode, auto-approval.

See [`SECURITY_MODEL.md`](SECURITY_MODEL.md) for the complete model, including
approval-mode details, logging/auditability, and the rationale for excluding
order execution.
