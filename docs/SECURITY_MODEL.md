# Security model (canonical)

This is the **source of truth** for what metatrader5-mcp is and is not allowed
to do. `docs/SAFETY.md` is a short compatibility summary that points here.

metatrader5-mcp is a **user-directed bridge** between an MCP client (Claude
Desktop, Claude Code, …), the user, and a locally running MetaTrader 5 terminal.
The owner can request a broad range of work — read market/account data, analyze
performance, develop and modify MQL5 code, prepare compiles and backtests, and
review reports. **It is not a trading bot and never executes trades.**

## The design principle in one sentence

**User authority is broad; model autonomy is narrow.** The owner may request
almost any development/analysis/preparation action, but the model may never take
a risky action on its own — risky actions require explicit human approval, with a
diff preview, a backup, a rollback point, and an audit entry.

## The owner-directed capability model (`policy.py`)

Every tool name maps to exactly one frozen `ToolPolicy`, the single source of
truth for what it may do. Two fields are kept deliberately separate:

- `user_can_request` — may the owner ever ask for this at all? (True for every tool.)
- `model_can_initiate` — may the model run it *without* an explicit, approved request?

Because an MCP server cannot itself tell whether the model or the user triggered a
call, `model_can_initiate=False` is enforced operationally by **requiring human
approval**: the human approving the call is the proof the owner directed it.

`ToolPolicy` also records capability/requirement flags (`requires_backup`,
`requires_diff_preview`, `requires_rollback_point`, `requires_audit_log`,
`requires_confirmation`, `requires_double_confirmation`, the `touches_*` surface
flags) and the **forbidden-capability** flags (`can_send_order`,
`can_modify_order`, `can_close_position`, `can_enable_autotrade`,
`stores_credentials`). Import-time invariants in `policy.py` assert that **no
policy may ever set a forbidden capability**, so the "no execution" boundary is
structural, not merely an absence of code.

### Permission levels

| Level | Name | Approval | Default | Examples |
|---|---|---|---|---|
| 0 | `SAFE_READ` | none | enabled | reads, analysis, `list_tool_policies`, `read_audit_log`, workspace listing, `mql5_file_read`, parse errors/warnings, CSV import |
| 1 | `CODE_DRAFT` | none | enabled | `mql5_file_diff`, `mql5_file_write_draft`, `mql5_file_backup`, `mql5_code_generate_*`, `metaeditor_prepare_compile`, `tester_prepare_signal_only_test` |
| 2 | `FILE_CHANGE` | single | enabled | `mql5_file_create/update/apply_patch/rename/delete/restore/revert_patch`, `workspace_restore_snapshot` |
| 3 | `LOCAL_RUNTIME` | single | enabled | order-planning tools, `metaeditor_run_compile`, `tester_run_backtest_if_supported` |
| 4 | `CHART_RUNTIME` | double | **disabled** | `mt5_chart_attach_ea`, `mt5_ea_write_inputs`, … (declared only) |
| 5 | `LIVE_SENSITIVE` | double | **disabled** | `mt5_live_enable_autotrade_request`, live readiness checks (declared only) |

Invariants enforced at import (`policy._check_invariants`): level ≥ 3 ⇒ not
model-initiable; level ≥ 4 ⇒ double confirmation **and** disabled by default;
every `FILE_CHANGE` tool requires backup + diff + rollback + audit; any
non-initiable tool must be approval-gated.

Level 4/5 tools are **declared in the manifest but not registered as MCP tools**
in this phase — they document intent and are fail-closed (dispatch refuses any
disabled tool). Operational chart/EA-runtime and live-account control are out of
scope here and reserved for a separate future phase.

## Stacked enforcement (every layer must allow an action)

### Layer 1 — Policy classification + gating (`action_router.dispatch`)

`server.py` never calls a tool module directly; every call goes through
`dispatch()`, which: looks up the policy (missing ⇒ **blocked**, fail-closed);
refuses anything carrying a forbidden capability or `enabled_by_default=False`;
audit-logs the request with its level/risk; requires approval when the policy
demands it (`requires_double_confirmation` ⇒ two-stage); executes; audit-logs
completion. `permissions.classify()` derives the coarse `SAFE_READ /
SAFE_ANALYSIS / REQUIRES_APPROVAL / BLOCKED` category from the same manifest, so
there is one source of truth. Execution-named actions (`send_order`,
`order_send`, `close_position`, …) are also listed explicitly in `BLOCKED` as
defense in depth.

#### Approval modes (`MT5_MCP_APPROVAL_MODE`)

- **`console`** (default): prints the action + params to stderr, waits for
  `yes`/`no` on stdin (and a typed confirmation of the action name for
  double-confirmation tools). Non-TTY ⇒ **denied**.
- **`file`**: writes `approvals/pending_<id>.json`, polls for
  `approvals/approved_<id>.txt` (plus `approved2_<id>.txt` for double
  confirmation) or `approvals/denied_<id>.txt`; timeout ⇒ **denied**.

**There is no auto-approval mode.**

### Layer 2 — Risk guard (order-planning tools)

`risk_guard.guard_order_tool()` runs inside every order-planning function,
independently of the approval gate: real/contest accounts are **always** refused
(no override), and demo accounts are refused unless
`MT5_MCP_ENABLE_DEMO_TRADING=true`. These tools only compute margin/profit and run
MT5's dry-run `order_check`; they never place an order.

### Layer 3 — File-change safeguards (`mql5_files.py`)

Every mutating file tool, before changing anything: backs up the prior content
into `MT5_MCP_BACKUPS_DIR`, writes a rollback-metadata record (used by
`mql5_file_revert_patch`), and returns a unified diff of the change. Combined with
Layer 1's approval requirement, a file change runs only after a human approved
that specific call, and is always reversible.

## Filesystem confinement (`paths.resolve_within`)

All file tools resolve caller paths strictly inside a configured base directory
and reject disallowed extensions, absolute paths that escape, and `..` traversal:

- reports / CSV imports → `MT5_MCP_REPORTS_DIR` (default `reports/`), `.html/.htm/.csv`;
- MQL5 sources → `MT5_MCP_WORKSPACE_DIR` (default `workspace/`), MQL5 suffixes only;
- backups/drafts → `MT5_MCP_BACKUPS_DIR` / `MT5_MCP_DRAFTS_DIR`.

## Windows/MT5-runtime adapters

MetaEditor compile and Strategy Tester run tools require Windows + a live
terminal. Off Windows (e.g. Linux CI) they return a structured
`UNSUPPORTED_IN_THIS_ENVIRONMENT` / `REQUIRES_WINDOWS_MT5_RUNTIME` payload instead
of raising, so the bridge stays importable and testable everywhere. The pure
prepare/parse helpers run anywhere.

## Logging and auditability

- `logs/actions.log` — one JSON line per action request (with policy level, risk,
  and params), per approval/blocked decision, and per completion. Readable through
  the `read_audit_log` tool.
- `logs/mt5_mcp.log` — application/error logging.

## What is intentionally NOT implemented

Absent by design — no code path to bypass:

- ❌ Order execution / `order_send`; modify / cancel / close / delete order tools.
- ❌ Live trading; AutoTrade enable; any real-account execution control.
- ❌ Operational chart/EA-runtime control (Level 4/5 are declared but disabled).
- ❌ Credential/session/cookie storage.
- ❌ Auto-approval (only `console`/`file` modes exist).
- ❌ Model-autonomous trading or any config that weakens `policy`, `risk_guard`,
  `action_router`, or `permissions`.

Adding real order execution is an explicit, separate decision reserved for a
future phase with its own threat model, repo/branch, multi-step approval,
kill-switch, and hard risk caps. In the current design, real execution is the
EA's deterministic job — not the LLM's or the MCP's.

## Related docs

- `docs/SAFETY.md` — short summary pointing here.
- `docs/ARCHITECTURE.md` — module layout and request flow.
- `docs/TOOLS.md` — per-tool reference.
- `docs/QUICKSTART_WINDOWS.md` — Windows setup and smoke test.
