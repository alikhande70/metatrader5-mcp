"""Regression-lock tests for the safety invariants that must never silently change.

These assert the structural safety surface of the policy model and the codebase:
no tool may carry an order-execution capability, the model may never auto-initiate a
risky tool, disabled tools stay disabled, execution-named actions stay blocked, and no
order_send / execution function exists anywhere in src/.
"""

from __future__ import annotations

from pathlib import Path

from mt5_mcp.permissions import BLOCKED, ActionCategory, classify
from mt5_mcp.policy import POLICIES, PermissionLevel
from mt5_mcp.server import mcp

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

_EXECUTION_NAMED_TOOLS = (
    "send_order",
    "place_order",
    "modify_order",
    "cancel_order",
    "delete_order",
    "close_position",
    "close_order",
    "execute_trade",
    "live_trade",
    "order_send",
)


def _registered_tool_names() -> set[str]:
    return {tool.name for tool in mcp._tool_manager.list_tools()}


# --- Policy model invariants -------------------------------------------------


def test_no_policy_carries_a_forbidden_capability():
    for policy in POLICIES.values():
        assert not policy.has_forbidden_capability, f"{policy.name} declares a forbidden capability"
        assert not policy.can_send_order
        assert not policy.can_modify_order
        assert not policy.can_close_position
        assert not policy.can_enable_autotrade
        assert not policy.stores_credentials


def test_user_can_always_request_every_tool():
    assert all(p.user_can_request for p in POLICIES.values())


def test_file_change_and_above_are_never_model_initiable():
    for policy in POLICIES.values():
        if policy.level >= PermissionLevel.FILE_CHANGE:
            assert not policy.model_can_initiate, f"{policy.name} must not be model-initiable"
            assert policy.requires_confirmation, f"{policy.name} must require confirmation"


def test_safe_read_and_pure_draft_tools_may_be_model_initiable_without_approval():
    # Correction: Level 0 reads and pure Level 1 draft/analysis tools are model-initiable
    # and approval-free. (Reads may touch account/orders in a read-only way; what they must
    # NOT do is mutate sources, run MetaEditor, touch live charts, or store credentials.)
    for policy in POLICIES.values():
        if policy.level <= PermissionLevel.CODE_DRAFT and policy.model_can_initiate:
            assert not policy.requires_approval, f"{policy.name} should not require approval"
            assert not policy.has_forbidden_capability
            assert not policy.touches_live_chart
            assert not policy.touches_metaeditor, f"{policy.name} must not run MetaEditor at draft level"


def test_chart_and_live_tools_are_disabled_by_default():
    for policy in POLICIES.values():
        if policy.level >= PermissionLevel.CHART_RUNTIME:
            assert not policy.enabled_by_default, f"{policy.name} must be disabled by default"
            assert policy.requires_double_confirmation


def test_file_change_tools_require_backup_diff_rollback_audit():
    for policy in POLICIES.values():
        if policy.level == PermissionLevel.FILE_CHANGE:
            assert policy.requires_backup
            assert policy.requires_diff_preview
            assert policy.requires_rollback_point
            assert policy.requires_audit_log
            assert policy.requires_approval


# --- Registration vs policy --------------------------------------------------


def test_every_registered_tool_has_an_enabled_policy():
    for name in _registered_tool_names():
        policy = POLICIES.get(name)
        assert policy is not None, f"registered tool '{name}' has no policy"
        assert policy.enabled_by_default, f"registered tool '{name}' must be enabled"
        assert classify(name) is not ActionCategory.BLOCKED


def test_no_disabled_tool_is_registered():
    disabled = {name for name, p in POLICIES.items() if not p.enabled_by_default}
    assert _registered_tool_names().isdisjoint(disabled)


# --- Execution-name fail-closed ----------------------------------------------


def test_no_execution_named_tool_is_registered():
    names = _registered_tool_names()
    for token in _EXECUTION_NAMED_TOOLS:
        assert token not in names


def test_execution_named_actions_classify_as_blocked():
    for token in _EXECUTION_NAMED_TOOLS:
        assert classify(token) is ActionCategory.BLOCKED
        assert token in BLOCKED


def test_unknown_action_is_blocked_fail_closed():
    for name in ("totally_unknown_action", "", "GET_ACCOUNT_INFO", "get_account_info "):
        assert classify(name) is ActionCategory.BLOCKED


# --- Source-level invariants -------------------------------------------------


def test_no_order_send_call_exists_in_src():
    offenders = []
    for path in SRC_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "order_send(" in line:
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, f"order_send(...) call found in src/: {offenders}"


def test_no_execution_function_defined_in_src():
    forbidden_defs = tuple(
        f"def {name}"
        for name in (
            "order_send",
            "send_order",
            "place_order",
            "modify_order",
            "cancel_order",
            "delete_order",
            "close_position",
            "close_order",
        )
    )
    offenders = []
    for path in SRC_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in forbidden_defs:
            if forbidden in text:
                offenders.append(f"{path}: {forbidden}")
    assert not offenders, f"forbidden function definition found in src/: {offenders}"
