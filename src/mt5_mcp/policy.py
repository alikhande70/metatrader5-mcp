"""Owner-directed capability model: the single source of truth for what each tool may do.

This module formalises the design principle "user authority broad, model autonomy
narrow". Every tool name maps to exactly one :class:`ToolPolicy`, which records two
independent things:

  1. ``user_can_request``   - may the owner ever ask for this operation at all?
  2. ``model_can_initiate`` - may the model run it without an explicit, human-approved
                              request?

An MCP server cannot, by itself, tell whether the *model* or the *user* triggered a
tool call. So ``model_can_initiate=False`` is enforced operationally by *requiring human
approval*: the human approving the call is the proof that the owner explicitly directed
it. The import-time invariants below guarantee that mapping can never drift.

Permission levels (0-5) order tools by how dangerous they are. Higher levels demand
more (approval, double confirmation) and the most dangerous ones are disabled by
default so there is no code path that runs them without a deliberate owner decision.

Nothing in this manifest may carry an order-execution capability. That is asserted at
import time, so the "no order_send" boundary is enforced structurally, not just by the
absence of code.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, IntEnum


class PermissionLevel(IntEnum):
    """How risky a tool is. Higher = more gating; >=4 is disabled by default."""

    SAFE_READ = 0  # read / analyse only
    CODE_DRAFT = 1  # produce drafts, diffs, plans - never touch a real source file
    FILE_CHANGE = 2  # mutate workspace files - needs approval + backup + diff + rollback
    LOCAL_RUNTIME = 3  # local terminal / MetaEditor action (compile, dry-run) - approval
    CHART_RUNTIME = 4  # attach EA / change chart - double confirmation, disabled by default
    LIVE_SENSITIVE = 5  # anything near a live account - disabled by default, future phase


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ToolPolicy:
    """Immutable capability descriptor for a single tool name."""

    name: str
    category: str
    level: PermissionLevel
    risk_level: RiskLevel

    # The two halves of the owner-directed model.
    user_can_request: bool
    model_can_initiate: bool

    # Gating requirements enforced by action_router.dispatch().
    requires_confirmation: bool
    requires_double_confirmation: bool
    requires_audit_log: bool

    # File-mutation safeguards enforced inside the file tools themselves.
    requires_backup: bool
    requires_diff_preview: bool
    requires_rollback_point: bool

    # What surfaces the tool touches (descriptive; used for invariants + audit).
    touches_filesystem: bool
    touches_mt5_terminal: bool
    touches_metaeditor: bool
    touches_strategy_tester: bool
    touches_live_chart: bool
    touches_account_state: bool
    touches_orders: bool

    # Hard-forbidden capabilities. These must be False for EVERY policy (asserted
    # at import time). They exist as explicit fields so the prohibition is visible
    # and machine-checkable, not merely implied by missing code.
    can_send_order: bool
    can_modify_order: bool
    can_close_position: bool
    can_enable_autotrade: bool
    stores_credentials: bool

    # Whether the tool runs at all. Levels >= CHART_RUNTIME are disabled by default.
    enabled_by_default: bool

    @property
    def requires_approval(self) -> bool:
        return self.requires_confirmation or self.requires_double_confirmation

    @property
    def has_forbidden_capability(self) -> bool:
        return (
            self.can_send_order
            or self.can_modify_order
            or self.can_close_position
            or self.can_enable_autotrade
            or self.stores_credentials
        )


# --- Factory helpers ---------------------------------------------------------
# Each builds a policy with the safe defaults for its level; callers override only
# the surface flags that differ (e.g. touches_mt5_terminal). All forbidden
# capabilities default to False and are never exposed as factory arguments.

_FORBIDDEN_DEFAULTS = dict(
    can_send_order=False,
    can_modify_order=False,
    can_close_position=False,
    can_enable_autotrade=False,
    stores_credentials=False,
)


def _surface(**flags: bool) -> dict[str, bool]:
    base = dict(
        touches_filesystem=False,
        touches_mt5_terminal=False,
        touches_metaeditor=False,
        touches_strategy_tester=False,
        touches_live_chart=False,
        touches_account_state=False,
        touches_orders=False,
    )
    base.update(flags)
    return base


def _safe_read(name: str, category: str, *, risk: RiskLevel = RiskLevel.NONE, **surface: bool) -> ToolPolicy:
    return ToolPolicy(
        name=name,
        category=category,
        level=PermissionLevel.SAFE_READ,
        risk_level=risk,
        user_can_request=True,
        model_can_initiate=True,
        requires_confirmation=False,
        requires_double_confirmation=False,
        requires_audit_log=True,
        requires_backup=False,
        requires_diff_preview=False,
        requires_rollback_point=False,
        enabled_by_default=True,
        **_surface(**surface),
        **_FORBIDDEN_DEFAULTS,
    )


def _code_draft(name: str, category: str, *, risk: RiskLevel = RiskLevel.LOW, **surface: bool) -> ToolPolicy:
    # Drafts/plans the model may produce freely; they never mutate a real source file.
    return ToolPolicy(
        name=name,
        category=category,
        level=PermissionLevel.CODE_DRAFT,
        risk_level=risk,
        user_can_request=True,
        model_can_initiate=True,
        requires_confirmation=False,
        requires_double_confirmation=False,
        requires_audit_log=True,
        requires_backup=False,
        requires_diff_preview=False,
        requires_rollback_point=False,
        enabled_by_default=True,
        **_surface(**surface),
        **_FORBIDDEN_DEFAULTS,
    )


def _file_change(name: str, category: str, *, risk: RiskLevel = RiskLevel.MEDIUM, **surface: bool) -> ToolPolicy:
    flags = _surface(**surface)
    flags["touches_filesystem"] = True  # a file change always touches the filesystem
    return ToolPolicy(
        name=name,
        category=category,
        level=PermissionLevel.FILE_CHANGE,
        risk_level=risk,
        user_can_request=True,
        model_can_initiate=False,
        requires_confirmation=True,
        requires_double_confirmation=False,
        requires_audit_log=True,
        requires_backup=True,
        requires_diff_preview=True,
        requires_rollback_point=True,
        enabled_by_default=True,
        **flags,
        **_FORBIDDEN_DEFAULTS,
    )


def _local_runtime(name: str, category: str, *, risk: RiskLevel = RiskLevel.MEDIUM, enabled: bool = True, **surface: bool) -> ToolPolicy:
    return ToolPolicy(
        name=name,
        category=category,
        level=PermissionLevel.LOCAL_RUNTIME,
        risk_level=risk,
        user_can_request=True,
        model_can_initiate=False,
        requires_confirmation=True,
        requires_double_confirmation=False,
        requires_audit_log=True,
        requires_backup=False,
        requires_diff_preview=False,
        requires_rollback_point=False,
        enabled_by_default=enabled,
        **_surface(**surface),
        **_FORBIDDEN_DEFAULTS,
    )


def _chart_runtime(name: str, category: str, *, risk: RiskLevel = RiskLevel.HIGH, **surface: bool) -> ToolPolicy:
    # Declared so the model is documented and fail-closed, but never enabled here.
    return ToolPolicy(
        name=name,
        category=category,
        level=PermissionLevel.CHART_RUNTIME,
        risk_level=risk,
        user_can_request=True,
        model_can_initiate=False,
        requires_confirmation=True,
        requires_double_confirmation=True,
        requires_audit_log=True,
        requires_backup=False,
        requires_diff_preview=False,
        requires_rollback_point=False,
        enabled_by_default=False,
        **_surface(**surface),
        **_FORBIDDEN_DEFAULTS,
    )


def _live_sensitive(name: str, category: str, *, risk: RiskLevel = RiskLevel.CRITICAL, **surface: bool) -> ToolPolicy:
    return ToolPolicy(
        name=name,
        category=category,
        level=PermissionLevel.LIVE_SENSITIVE,
        risk_level=risk,
        user_can_request=True,
        model_can_initiate=False,
        requires_confirmation=True,
        requires_double_confirmation=True,
        requires_audit_log=True,
        requires_backup=False,
        requires_diff_preview=False,
        requires_rollback_point=False,
        enabled_by_default=False,
        **_surface(**surface),
        **_FORBIDDEN_DEFAULTS,
    )


# --- The manifest ------------------------------------------------------------

_ALL: list[ToolPolicy] = [
    # ----- Introspection / audit (Level 0) -----
    _safe_read("list_tool_policies", "introspection"),
    _safe_read("get_tool_policy", "introspection"),
    _safe_read("read_audit_log", "log_read", touches_filesystem=True),
    # ----- Existing market/account reads (Level 0) -----
    _safe_read("get_account_info", "account_read", touches_mt5_terminal=True, touches_account_state=True),
    _safe_read("get_terminal_info", "account_read", touches_mt5_terminal=True),
    _safe_read("get_symbol_info", "market_read", touches_mt5_terminal=True),
    _safe_read("get_tick", "market_read", touches_mt5_terminal=True),
    _safe_read("get_rates", "market_read", touches_mt5_terminal=True),
    _safe_read("get_positions", "account_read", touches_mt5_terminal=True, touches_account_state=True),
    _safe_read("get_orders", "account_read", touches_mt5_terminal=True, touches_account_state=True, touches_orders=True),
    _safe_read("get_history_deals", "account_read", touches_mt5_terminal=True, touches_account_state=True),
    _safe_read("read_log", "log_read", touches_filesystem=True),
    _safe_read("read_strategy_report", "report_read", touches_filesystem=True, touches_strategy_tester=True),
    # ----- Existing analysis (Level 0) -----
    _safe_read("summarize_positions", "analysis"),
    _safe_read("analyze_drawdown", "analysis"),
    _safe_read("analyze_trade_history", "analysis"),
    _safe_read("calculate_profit_risk_basic", "analysis"),
    # ----- Order planning (Level 3: approval; risk_guard restricts to demo) -----
    _local_runtime("calculate_margin", "order_planning", touches_mt5_terminal=True, touches_account_state=True),
    _local_runtime("calculate_profit", "order_planning", touches_mt5_terminal=True, touches_account_state=True),
    _local_runtime("check_order", "order_planning", touches_mt5_terminal=True, touches_account_state=True, touches_orders=True),
    _local_runtime("prepare_order_plan", "order_planning", touches_mt5_terminal=True, touches_account_state=True, touches_orders=True),
    # ----- Workspace reads (Level 0) -----
    _safe_read("workspace_show_status", "workspace", touches_filesystem=True),
    _safe_read("workspace_detect_data_folder", "workspace", touches_filesystem=True),
    _safe_read("workspace_list_experts", "workspace", touches_filesystem=True),
    _safe_read("workspace_list_indicators", "workspace", touches_filesystem=True),
    _safe_read("workspace_list_scripts", "workspace", touches_filesystem=True),
    _safe_read("workspace_list_includes", "workspace", touches_filesystem=True),
    # ----- Workspace snapshot (Level 1 create / Level 2 restore) -----
    _code_draft("workspace_snapshot", "workspace", touches_filesystem=True),
    _file_change("workspace_restore_snapshot", "workspace", risk=RiskLevel.HIGH),
    # ----- Code reads / drafts (Level 0/1) -----
    _safe_read("mql5_file_read", "code", touches_filesystem=True),
    _safe_read("mql5_code_review", "code", touches_filesystem=True),
    _code_draft("mql5_file_diff", "code", touches_filesystem=True),
    _code_draft("mql5_file_write_draft", "code", touches_filesystem=True),
    _code_draft("mql5_file_backup", "code", touches_filesystem=True),
    _code_draft("mql5_code_generate_ea", "code_gen", touches_filesystem=True),
    _code_draft("mql5_code_generate_indicator", "code_gen", touches_filesystem=True),
    _code_draft("mql5_code_generate_script", "code_gen", touches_filesystem=True),
    _code_draft("mql5_code_fix_compile_error", "code_gen"),
    # ----- Code mutations (Level 2: approval + backup + diff + rollback) -----
    _file_change("mql5_file_create", "code"),
    _file_change("mql5_file_update", "code"),
    _file_change("mql5_file_apply_patch", "code"),
    _file_change("mql5_file_revert_patch", "code"),
    _file_change("mql5_file_restore", "code"),
    _file_change("mql5_file_rename", "code"),
    _file_change("mql5_file_delete", "code", risk=RiskLevel.HIGH),
    # ----- Report / backtest import + review (Level 0/1) -----
    _safe_read("tester_import_csv", "tester", touches_filesystem=True, touches_strategy_tester=True),
    _safe_read("tester_review_results", "tester"),
    _safe_read("tester_compare_runs", "tester"),
    _code_draft("tester_generate_backtest_report", "tester"),
    # ----- MetaEditor / Tester adapters (Level 0/1 prepare+parse, Level 3 run) -----
    _safe_read("metaeditor_detect_path", "metaeditor"),
    _safe_read("metaeditor_read_compile_log", "metaeditor", touches_filesystem=True),
    _safe_read("metaeditor_parse_errors", "metaeditor"),
    _safe_read("metaeditor_parse_warnings", "metaeditor"),
    _code_draft("metaeditor_prepare_compile", "metaeditor"),
    _code_draft("metaeditor_generate_fix_plan", "metaeditor"),
    _code_draft("tester_prepare_signal_only_test", "tester"),
    _local_runtime("metaeditor_run_compile", "metaeditor", touches_metaeditor=True, touches_filesystem=True),
    _local_runtime("tester_run_backtest_if_supported", "tester", touches_strategy_tester=True, touches_filesystem=True),
    # ----- Declared but DISABLED: chart / EA runtime (Level 4) -----
    _chart_runtime("mt5_chart_list_open_charts", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_chart_open_symbol", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_chart_set_timeframe", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_chart_apply_template", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_chart_attach_ea", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_chart_remove_ea", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_ea_read_inputs", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_ea_write_inputs", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_ea_set_mode_signal_only", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_ea_set_mode_demo_test", "chart_runtime", touches_live_chart=True, touches_mt5_terminal=True),
    _chart_runtime("mt5_ea_prepare_live_mode_checklist", "chart_runtime", touches_live_chart=True),
    # ----- Declared but DISABLED: live-sensitive (Level 5, future phase) -----
    _live_sensitive("mt5_live_readiness_check", "live", touches_account_state=True),
    _live_sensitive("mt5_live_risk_caps_verify", "live", touches_account_state=True),
    _live_sensitive("mt5_live_prepare_activation_checklist", "live", touches_account_state=True),
    _live_sensitive("mt5_live_enable_autotrade_request", "live", touches_account_state=True, touches_mt5_terminal=True),
]

POLICIES: dict[str, ToolPolicy] = {p.name: p for p in _ALL}


def get_policy(name: str) -> ToolPolicy | None:
    """Return the policy for ``name``, or None (which callers must treat as blocked)."""
    return POLICIES.get(name)


def with_overrides(name: str, **overrides: object) -> ToolPolicy:
    """Test/utility helper: a copy of a policy with fields replaced (does not mutate the manifest)."""
    base = POLICIES[name]
    return replace(base, **overrides)  # type: ignore[arg-type]


# --- Import-time invariants (fail fast) --------------------------------------
# These encode the design rules so a future edit that violates them cannot even
# be imported, let alone shipped.

def _check_invariants() -> None:
    """Enforce the risk/mutation-based rules of the capability model.

    Rules (deliberately NOT "non-initiable => confirmation"; safe Level 0 reads and
    pure Level 1 drafts/analysis may be model-initiated and approval-free):

      - No policy may carry a forbidden capability (order/autotrade/credentials).
      - The user may always request any tool.
      - Level >= FILE_CHANGE (any mutation/runtime/chart/live): NOT model-initiable
        and must require confirmation.
      - Level >= CHART_RUNTIME: must require double confirmation.
      - Level == LIVE_SENSITIVE: must be disabled by default.
      - A source-file mutation (FILE_CHANGE) must require backup + diff + rollback + audit.
    """
    for p in _ALL:
        if p.has_forbidden_capability:
            raise AssertionError(
                f"Policy '{p.name}' declares a forbidden capability (order/autotrade/credentials). "
                "No tool may ever carry these."
            )
        if not p.user_can_request:
            raise AssertionError(f"Policy '{p.name}' has user_can_request=False; the user may always request tools.")
        if p.level >= PermissionLevel.FILE_CHANGE:
            if p.model_can_initiate:
                raise AssertionError(f"Policy '{p.name}' (level {p.level.name}) must not be model-initiable.")
            if not p.requires_confirmation:
                raise AssertionError(f"Policy '{p.name}' (level {p.level.name}) must require confirmation.")
        if p.level >= PermissionLevel.CHART_RUNTIME and not p.requires_double_confirmation:
            raise AssertionError(f"Policy '{p.name}' (level {p.level.name}) must require double confirmation.")
        if p.level == PermissionLevel.LIVE_SENSITIVE and p.enabled_by_default:
            raise AssertionError(f"Policy '{p.name}' (LIVE_SENSITIVE) must be disabled by default.")
        if p.level == PermissionLevel.FILE_CHANGE and not (
            p.requires_backup and p.requires_diff_preview and p.requires_rollback_point and p.requires_audit_log
        ):
            raise AssertionError(
                f"File-change policy '{p.name}' must require backup, diff preview, rollback point, and audit log."
            )

    duplicates = [p.name for p in _ALL if list(n.name for n in _ALL).count(p.name) > 1]
    if duplicates:
        raise AssertionError(f"Duplicate tool names in manifest: {sorted(set(duplicates))}")


_check_invariants()
