"""Audit + policy introspection tools (Level 0).

These let the owner inspect the capability model and the audit trail through the MCP
client itself, without leaving the safe-read tier. `read_audit_log` only reads the
bridge's own JSONL action log under the configured log directory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dataclasses import asdict

from .policy import POLICIES, get_policy


def _log_dir() -> Path:
    return Path(os.environ.get("MT5_MCP_LOG_DIR", "logs")).resolve()


def list_tool_policies() -> dict[str, Any]:
    """List every registered tool name with its permission level, risk, and key gating flags."""
    items = []
    for name, p in sorted(POLICIES.items()):
        items.append(
            {
                "name": name,
                "category": p.category,
                "level": int(p.level),
                "level_name": p.level.name,
                "risk_level": p.risk_level.value,
                "user_can_request": p.user_can_request,
                "model_can_initiate": p.model_can_initiate,
                "requires_approval": p.requires_approval,
                "requires_double_confirmation": p.requires_double_confirmation,
                "enabled_by_default": p.enabled_by_default,
            }
        )
    return {"count": len(items), "policies": items}


def get_tool_policy(name: str) -> dict[str, Any]:
    """Return the full policy for a single tool name (all capability fields)."""
    policy = get_policy(name)
    if policy is None:
        return {"name": name, "found": False, "note": "No policy registered; this action fails closed (blocked)."}
    data = asdict(policy)
    data["level"] = int(policy.level)
    data["level_name"] = policy.level.name
    data["risk_level"] = policy.risk_level.value
    data["found"] = True
    return data


def read_audit_log(lines: int = 100) -> dict[str, Any]:
    """Read the tail of the JSONL action/audit log (logs/actions.log)."""
    log_path = _log_dir() / "actions.log"
    if not log_path.exists():
        return {"path": str(log_path), "exists": False, "events": []}
    raw = log_path.read_text(encoding="utf-8").splitlines()
    tail = raw[-lines:] if lines > 0 else raw
    events: list[Any] = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"raw": line})
    return {"path": str(log_path), "exists": True, "returned": len(events), "events": events}
