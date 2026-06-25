"""Single choke point every tool call passes through: classify -> approve -> log -> execute.

server.py never calls mt5_bridge/analysis_tools/order_tools directly - it always
goes through `dispatch()` so that permission classification, approval gating, and
action logging cannot be accidentally skipped for any tool.
"""

from __future__ import annotations

from typing import Any, Callable

from .approval_gate import ApprovalGate
from .permissions import ActionCategory, classify
from .utils import get_logger, log_action_event, new_id

logger = get_logger(__name__)


class BlockedActionError(PermissionError):
    """Raised when an action is classified BLOCKED (including unknown actions)."""


class ApprovalDeniedError(PermissionError):
    """Raised when a REQUIRES_APPROVAL action is not approved by a human."""


def dispatch(
    action_name: str,
    executor: Callable[[], Any],
    params: dict[str, Any] | None = None,
    *,
    approval_gate: ApprovalGate | None = None,
    description: str | None = None,
) -> Any:
    """Classify `action_name`, enforce approval if required, run `executor()`, and log every step."""
    params = params or {}
    category = classify(action_name)
    action_id = new_id("act")

    log_action_event(
        {
            "event": "action_request",
            "action_id": action_id,
            "action": action_name,
            "category": category.value,
            "params": params,
        }
    )
    logger.info("Action requested: %s [%s] id=%s", action_name, category.value, action_id)

    if category is ActionCategory.BLOCKED:
        log_action_event(
            {
                "event": "action_decision",
                "action_id": action_id,
                "action": action_name,
                "decision": "blocked",
            }
        )
        raise BlockedActionError(
            f"Action '{action_name}' is blocked in Phase 1 (no order execution or live trading is implemented)."
        )

    if category is ActionCategory.REQUIRES_APPROVAL:
        if approval_gate is None:
            raise ApprovalDeniedError(
                f"Action '{action_name}' requires approval but no approval gate is configured."
            )
        approved = approval_gate.request_approval(
            action_id=action_id,
            action_name=action_name,
            description=description or action_name,
            params=params,
        )
        log_action_event(
            {
                "event": "action_decision",
                "action_id": action_id,
                "action": action_name,
                "decision": "approved" if approved else "denied",
            }
        )
        if not approved:
            raise ApprovalDeniedError(f"Action '{action_name}' was not approved.")

    result = executor()

    log_action_event(
        {
            "event": "action_completed",
            "action_id": action_id,
            "action": action_name,
        }
    )
    return result
