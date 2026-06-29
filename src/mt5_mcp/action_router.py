"""Single choke point every tool call passes through: classify -> gate -> log -> execute.

server.py never calls the tool modules directly - it always goes through `dispatch()`
so that policy classification, approval gating, and audit logging cannot be accidentally
skipped for any tool. Gating decisions come from `policy.POLICIES` (the capability
manifest); `permissions.classify()` provides the coarse category used for the audit log.
"""

from __future__ import annotations

from typing import Any, Callable

from .approval_gate import ApprovalGate
from .permissions import BLOCKED, ActionCategory, classify
from .policy import get_policy
from .utils import get_logger, log_action_event, new_id

logger = get_logger(__name__)


class BlockedActionError(PermissionError):
    """Raised when an action is blocked (unknown, disabled, or carrying a forbidden capability)."""


class ApprovalDeniedError(PermissionError):
    """Raised when an approval-requiring action is not approved by a human."""


def _policy_summary(action_name: str) -> dict[str, Any]:
    policy = get_policy(action_name)
    if policy is None:
        return {"policy": None}
    return {
        "level": int(policy.level),
        "level_name": policy.level.name,
        "risk_level": policy.risk_level.value,
        "model_can_initiate": policy.model_can_initiate,
        "requires_double_confirmation": policy.requires_double_confirmation,
        "enabled_by_default": policy.enabled_by_default,
    }


def dispatch(
    action_name: str,
    executor: Callable[[], Any],
    params: dict[str, Any] | None = None,
    *,
    approval_gate: ApprovalGate | None = None,
    description: str | None = None,
) -> Any:
    """Classify `action_name`, enforce gating, run `executor()`, and audit-log every step."""
    params = params or {}
    category = classify(action_name)
    policy = get_policy(action_name)
    action_id = new_id("act")

    log_action_event(
        {
            "event": "action_request",
            "action_id": action_id,
            "action": action_name,
            "category": category.value,
            "params": params,
            **_policy_summary(action_name),
        }
    )
    logger.info("Action requested: %s [%s] id=%s", action_name, category.value, action_id)

    if category is ActionCategory.BLOCKED:
        log_action_event(
            {"event": "action_decision", "action_id": action_id, "action": action_name, "decision": "blocked"}
        )
        if action_name in BLOCKED:
            reason = "it names an order-execution operation, which is never implemented or allowed"
        elif policy is None:
            reason = "it has no registered policy (unknown actions fail closed)"
        elif policy.has_forbidden_capability:
            reason = "its policy declares a forbidden capability"
        else:
            reason = "it is disabled by default (gated to a future phase / owner enablement)"
        raise BlockedActionError(f"Action '{action_name}' is blocked: {reason}.")

    if category is ActionCategory.REQUIRES_APPROVAL:
        if approval_gate is None:
            raise ApprovalDeniedError(
                f"Action '{action_name}' requires approval but no approval gate is configured."
            )
        require_double = bool(policy and policy.requires_double_confirmation)
        approved = approval_gate.request_approval(
            action_id=action_id,
            action_name=action_name,
            description=description or action_name,
            params=params,
            require_double=require_double,
        )
        log_action_event(
            {
                "event": "action_decision",
                "action_id": action_id,
                "action": action_name,
                "decision": "approved" if approved else "denied",
                "double_confirmation": require_double,
            }
        )
        if not approved:
            raise ApprovalDeniedError(f"Action '{action_name}' was not approved.")

    result = executor()

    log_action_event(
        {"event": "action_completed", "action_id": action_id, "action": action_name}
    )
    return result
