"""Action classification, derived from the policy manifest in policy.py.

`ActionCategory` is kept as the coarse signal `action_router` has always used
(SAFE / approval / blocked), but it is now *derived* from `policy.POLICIES` so there
is a single source of truth. The richer per-tool capability flags live on
`ToolPolicy`; this module only answers "does this need approval, or is it blocked?".

Fail-closed: an unknown name, a name with no policy, a disabled tool, or anything
carrying a forbidden capability all classify as BLOCKED.
"""

from __future__ import annotations

from enum import Enum

from .policy import POLICIES, get_policy


class ActionCategory(str, Enum):
    SAFE_READ = "SAFE_READ"
    SAFE_ANALYSIS = "SAFE_ANALYSIS"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    BLOCKED = "BLOCKED"


# Explicit execution names. No tool implements these; they are listed so the router
# refuses them on sight (defense in depth) even if a future change wires one up.
BLOCKED: frozenset[str] = frozenset(
    {
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
    }
)


def classify(action_name: str) -> ActionCategory:
    """Classify an action name, defaulting unknown/disabled/forbidden actions to BLOCKED."""
    if action_name in BLOCKED:
        return ActionCategory.BLOCKED

    policy = get_policy(action_name)
    if policy is None or not policy.enabled_by_default or policy.has_forbidden_capability:
        return ActionCategory.BLOCKED

    if policy.requires_approval:
        return ActionCategory.REQUIRES_APPROVAL
    if policy.category == "analysis":
        return ActionCategory.SAFE_ANALYSIS
    return ActionCategory.SAFE_READ


def _names_in(category: ActionCategory) -> frozenset[str]:
    return frozenset(name for name in POLICIES if classify(name) is category)


# Derived category sets (single source of truth = the policy manifest). Kept as
# module-level frozensets for the safety tests and docs that introspect them.
SAFE_READ: frozenset[str] = _names_in(ActionCategory.SAFE_READ)
SAFE_ANALYSIS: frozenset[str] = _names_in(ActionCategory.SAFE_ANALYSIS)
REQUIRES_APPROVAL: frozenset[str] = _names_in(ActionCategory.REQUIRES_APPROVAL)
