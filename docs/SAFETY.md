# Safety model (summary)

> **This is a short summary. The canonical safety document is
> [`SECURITY_MODEL.md`](SECURITY_MODEL.md) — read it for the full, authoritative
> details.** This page is kept so existing links to `SAFETY.md` still work.

metatrader5-mcp is a **user-directed bridge** (read / analysis / MQL5
development / compile+backtest preparation), not a trading bot. The design
principle is **user authority broad, model autonomy narrow**.

**Capability model:** every tool maps to a `ToolPolicy` (`policy.py`) with a
permission level (0–5) and two independent flags — `user_can_request` (always
true) and `model_can_initiate` (false for anything risky). Import-time invariants
forbid any tool from declaring an order/AutoTrade/credential capability.

**Stacked enforcement, all required, none disableable:**

1. **Policy classification + gating** — every call goes through
   `action_router.dispatch()`. Missing/disabled/forbidden ⇒ **blocked**
   (fail-closed). Approval-requiring tools need explicit human approval
   (`console`/`file`); high-risk tools need **double** confirmation. **No
   auto-approval mode exists.**
2. **Risk guard** — order-planning tools are always refused on real/contest
   accounts (no override) and on demo unless `MT5_MCP_ENABLE_DEMO_TRADING=true`.
3. **File-change safeguards** — every mutating file tool makes a backup, writes a
   rollback record, and returns a diff before changing anything.

**File-path confinement (`paths.resolve_within`):** reports/CSV under
`MT5_MCP_REPORTS_DIR`, MQL5 sources under `MT5_MCP_WORKSPACE_DIR`, backups/drafts
under their dirs; absolute paths and `..` traversal that escape are rejected.

**Not implemented on purpose (absent, not just gated):** order execution,
`order_send`, modify/cancel/close/delete order tools, live trading, AutoTrade
enable, credential storage, auto-approval. Chart/EA-runtime and live-account
tools (Level 4/5) are **declared in the policy model but disabled by default**.

See [`SECURITY_MODEL.md`](SECURITY_MODEL.md) for the complete model, including
approval-mode details, logging/auditability, and the rationale for excluding
order execution.
