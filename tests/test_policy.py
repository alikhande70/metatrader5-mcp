from __future__ import annotations

import pytest

from mt5_mcp.policy import POLICIES, PermissionLevel, RiskLevel, ToolPolicy, get_policy


def test_manifest_is_non_empty_and_keyed_by_name():
    assert POLICIES
    for name, policy in POLICIES.items():
        assert policy.name == name
        assert isinstance(policy, ToolPolicy)


def test_get_policy_unknown_returns_none():
    assert get_policy("definitely_not_a_tool") is None


def test_levels_and_risk_are_valid_enums():
    for policy in POLICIES.values():
        assert isinstance(policy.level, PermissionLevel)
        assert isinstance(policy.risk_level, RiskLevel)


def test_non_initiable_tools_require_approval():
    for policy in POLICIES.values():
        if not policy.model_can_initiate:
            assert policy.requires_approval, f"{policy.name}: non-initiable but no approval required"


def test_safe_read_tools_are_model_initiable_without_approval():
    for policy in POLICIES.values():
        if policy.level == PermissionLevel.SAFE_READ:
            assert policy.model_can_initiate
            assert not policy.requires_approval


def test_invariants_are_enforced_at_import():
    # Constructing a policy that violates the rules must be rejected by _check_invariants
    # when added to the manifest. We assert the live manifest already satisfies them.
    from mt5_mcp import policy as policy_module

    policy_module._check_invariants()  # should not raise


def test_chart_and_live_categories_present_but_disabled():
    chart = [p for p in POLICIES.values() if p.level == PermissionLevel.CHART_RUNTIME]
    live = [p for p in POLICIES.values() if p.level == PermissionLevel.LIVE_SENSITIVE]
    assert chart and live
    assert all(not p.enabled_by_default for p in chart + live)


def test_order_planning_tools_are_runtime_level_and_gated():
    for name in ("calculate_margin", "calculate_profit", "check_order", "prepare_order_plan"):
        p = get_policy(name)
        assert p is not None
        assert p.level == PermissionLevel.LOCAL_RUNTIME
        assert p.requires_approval
        assert not p.model_can_initiate
