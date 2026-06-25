from __future__ import annotations

import json

import pytest

from mt5_mcp import action_router, utils
from mt5_mcp.approval_gate import ApprovalGate


class StubApprovalGate(ApprovalGate):
    def __init__(self, approve: bool):
        self.approve = approve
        self.calls: list[dict] = []

    def request_approval(self, action_id, action_name, description, params):
        self.calls.append({"action_id": action_id, "action_name": action_name})
        return self.approve


def test_safe_read_runs_executor_without_approval_gate():
    calls = []
    result = action_router.dispatch("get_account_info", lambda: calls.append(1) or "ok", {})
    assert result == "ok"
    assert calls == [1]


def test_blocked_action_never_calls_executor():
    calls = []
    with pytest.raises(action_router.BlockedActionError):
        action_router.dispatch("send_order", lambda: calls.append(1), {})
    assert calls == []


def test_unknown_action_is_blocked():
    with pytest.raises(action_router.BlockedActionError):
        action_router.dispatch("not_a_real_action", lambda: "should not run", {})


def test_requires_approval_runs_executor_when_approved():
    gate = StubApprovalGate(approve=True)
    result = action_router.dispatch("check_order", lambda: "checked", {"symbol": "EURUSD"}, approval_gate=gate)
    assert result == "checked"
    assert len(gate.calls) == 1


def test_requires_approval_denied_raises_and_skips_executor():
    gate = StubApprovalGate(approve=False)
    calls = []
    with pytest.raises(action_router.ApprovalDeniedError):
        action_router.dispatch("prepare_order_plan", lambda: calls.append(1), {}, approval_gate=gate)
    assert calls == []


def test_requires_approval_without_gate_configured_raises():
    with pytest.raises(action_router.ApprovalDeniedError):
        action_router.dispatch("calculate_margin", lambda: "never", {})


def test_action_request_and_decision_are_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "LOG_DIR", tmp_path)
    gate = StubApprovalGate(approve=True)
    action_router.dispatch("check_order", lambda: "ok", {"symbol": "EURUSD"}, approval_gate=gate)

    log_file = tmp_path / "actions.log"
    lines = log_file.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line)["event"] for line in lines]
    assert "action_request" in events
    assert "action_decision" in events
    assert "action_completed" in events
