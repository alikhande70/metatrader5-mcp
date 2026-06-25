from __future__ import annotations

import pytest

from mt5_mcp import approval_gate
from mt5_mcp.approval_gate import ConsoleApprovalGate, FileApprovalGate, get_approval_gate


def test_console_gate_denies_when_no_tty(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    gate = ConsoleApprovalGate()
    assert gate.request_approval("a1", "check_order", "desc", {}) is False


def test_console_gate_approves_on_yes(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    gate = ConsoleApprovalGate()
    assert gate.request_approval("a1", "check_order", "desc", {}) is True


def test_console_gate_denies_on_no(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    gate = ConsoleApprovalGate()
    assert gate.request_approval("a1", "check_order", "desc", {}) is False


def test_console_gate_denies_on_garbage_input(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "sure whatever")
    gate = ConsoleApprovalGate()
    assert gate.request_approval("a1", "check_order", "desc", {}) is False


def test_file_gate_approves_when_file_appears(tmp_path, monkeypatch):
    monkeypatch.setattr(approval_gate, "APPROVALS_DIR", tmp_path)
    gate = FileApprovalGate(poll_interval_s=0.01, timeout_s=2.0)

    (tmp_path / "approved_a1.txt").write_text("yes", encoding="utf-8")
    approved = gate.request_approval("a1", "prepare_order_plan", "desc", {})
    assert approved is True
    assert not (tmp_path / "pending_a1.json").exists()


def test_file_gate_denies_when_denied_file_appears(tmp_path, monkeypatch):
    monkeypatch.setattr(approval_gate, "APPROVALS_DIR", tmp_path)
    gate = FileApprovalGate(poll_interval_s=0.01, timeout_s=2.0)

    (tmp_path / "denied_a2.txt").write_text("no", encoding="utf-8")
    approved = gate.request_approval("a2", "prepare_order_plan", "desc", {})
    assert approved is False


def test_file_gate_denies_on_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(approval_gate, "APPROVALS_DIR", tmp_path)
    gate = FileApprovalGate(poll_interval_s=0.01, timeout_s=0.05)
    approved = gate.request_approval("a3", "prepare_order_plan", "desc", {})
    assert approved is False
    assert not (tmp_path / "pending_a3.json").exists()


def test_get_approval_gate_modes(monkeypatch):
    assert isinstance(get_approval_gate("console"), ConsoleApprovalGate)
    assert isinstance(get_approval_gate("file"), FileApprovalGate)
    with pytest.raises(ValueError):
        get_approval_gate("auto_approve_everything")


def test_no_auto_approval_mode_exists():
    """There must be no mode string that grants approval without a human action."""
    for mode in ["auto", "always", "yes", "skip", "none"]:
        with pytest.raises(ValueError):
            get_approval_gate(mode)
