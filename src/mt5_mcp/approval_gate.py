"""Human approval gate for REQUIRES_APPROVAL actions.

Two modes, selected via MT5_MCP_APPROVAL_MODE:
  - "console": prompts the terminal running the MCP server with a y/n question.
  - "file": writes approvals/pending_<id>.json and waits for a human to create
    approvals/approved_<id>.txt (any content) or approvals/denied_<id>.txt.

There is no auto-approval mode. If approval cannot be obtained (no TTY for
console mode, timeout for file mode, anything other than an explicit "yes"),
the action is denied.
"""

from __future__ import annotations

import json
import os
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .utils import get_logger, utcnow_iso

logger = get_logger(__name__)

APPROVALS_DIR = Path(os.environ.get("MT5_MCP_APPROVALS_DIR", "approvals"))


class ApprovalGate(ABC):
    @abstractmethod
    def request_approval(
        self,
        action_id: str,
        action_name: str,
        description: str,
        params: dict[str, Any],
    ) -> bool:
        """Return True only if a human explicitly approved this action."""


class ConsoleApprovalGate(ApprovalGate):
    """Blocks and asks the operator running the server process for a y/n answer."""

    def request_approval(
        self,
        action_id: str,
        action_name: str,
        description: str,
        params: dict[str, Any],
    ) -> bool:
        if not sys.stdin.isatty():
            logger.warning(
                "Console approval requested for %s (%s) but stdin is not a TTY; denying by default.",
                action_name,
                action_id,
            )
            return False

        print("\n=== APPROVAL REQUIRED ===", file=sys.stderr)
        print(f"action_id : {action_id}", file=sys.stderr)
        print(f"action    : {action_name}", file=sys.stderr)
        print(f"details   : {description}", file=sys.stderr)
        print(f"params    : {json.dumps(params, default=str)}", file=sys.stderr)
        answer = input("Approve this action? [yes/no]: ").strip().lower()
        return answer in {"y", "yes"}


class FileApprovalGate(ApprovalGate):
    """Writes a pending request file and waits for approved_<id>.txt / denied_<id>.txt."""

    def __init__(self, poll_interval_s: float = 1.0, timeout_s: float = 300.0):
        self.poll_interval_s = poll_interval_s
        self.timeout_s = timeout_s

    def request_approval(
        self,
        action_id: str,
        action_name: str,
        description: str,
        params: dict[str, Any],
    ) -> bool:
        APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
        pending_path = APPROVALS_DIR / f"pending_{action_id}.json"
        approved_path = APPROVALS_DIR / f"approved_{action_id}.txt"
        denied_path = APPROVALS_DIR / f"denied_{action_id}.txt"

        pending_path.write_text(
            json.dumps(
                {
                    "action_id": action_id,
                    "action": action_name,
                    "description": description,
                    "params": params,
                    "requested_at": utcnow_iso(),
                    "instructions": (
                        f"To approve, create '{approved_path.name}' in this directory. "
                        f"To deny, create '{denied_path.name}' (or just let this request time out)."
                    ),
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        logger.info("Wrote pending approval request %s for action %s", pending_path, action_name)

        deadline = time.monotonic() + self.timeout_s
        try:
            while time.monotonic() < deadline:
                if approved_path.exists():
                    logger.info("Approval granted via %s", approved_path)
                    return True
                if denied_path.exists():
                    logger.info("Approval denied via %s", denied_path)
                    return False
                time.sleep(self.poll_interval_s)
        finally:
            pending_path.unlink(missing_ok=True)

        logger.warning("Approval request %s timed out after %.0fs; denying by default.", action_id, self.timeout_s)
        return False


def get_approval_gate(mode: str | None = None) -> ApprovalGate:
    """Build the configured ApprovalGate. Defaults to console mode."""
    mode = (mode or os.environ.get("MT5_MCP_APPROVAL_MODE", "console")).strip().lower()
    if mode == "console":
        return ConsoleApprovalGate()
    if mode == "file":
        return FileApprovalGate()
    raise ValueError(f"Unknown approval mode '{mode}'. Expected 'console' or 'file'.")
