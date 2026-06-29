"""MetaEditor adapter: prepare/parse (pure, cross-platform) + a gated `run_compile`.

The pure helpers (`prepare_compile`, `parse_errors`, `parse_warnings`,
`generate_fix_plan`) run anywhere and are fully testable. `detect_path` and
`run_compile` need Windows + a MetaEditor install; off Windows (e.g. Linux CI) they
return a structured ``UNSUPPORTED_IN_THIS_ENVIRONMENT`` / ``REQUIRES_WINDOWS_MT5_RUNTIME``
payload instead of raising, so the bridge stays importable and testable everywhere.

`run_compile` is Level 3 (approval-gated by action_router) and never performs trade
execution - it only invokes the compiler.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import code_gen, workspace_tools as ws
from .paths import resolve_within
from .utils import get_logger

logger = get_logger(__name__)

UNSUPPORTED = "UNSUPPORTED_IN_THIS_ENVIRONMENT"
REQUIRES_WINDOWS = "REQUIRES_WINDOWS_MT5_RUNTIME"

# MetaEditor log line, e.g.: "MyEA.mq5(34,10) : error 245: 'x' - undeclared identifier"
_LOG_LINE = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\)\s*:\s*(?P<sev>error|warning)\s+(?P<code>\d+):\s*(?P<msg>.*)$",
    re.IGNORECASE,
)
_RESULT_LINE = re.compile(r"(?P<errors>\d+)\s+errors?,\s*(?P<warnings>\d+)\s+warnings?", re.IGNORECASE)


def detect_path() -> dict[str, Any]:
    """Locate metaeditor64.exe via METAEDITOR_PATH or common install dirs (Windows only)."""
    configured = os.environ.get("METAEDITOR_PATH")
    if configured:
        return {"status": "configured", "path": configured, "exists": Path(configured).exists()}
    if sys.platform != "win32":
        return {
            "status": UNSUPPORTED,
            "note": "MetaEditor runs on Windows. Set METAEDITOR_PATH to metaeditor64.exe to use compile tools.",
        }
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "MetaTrader 5" / "metaeditor64.exe",
    ]
    for c in candidates:
        if c.exists():
            return {"status": "detected", "path": str(c), "exists": True}
    return {"status": "not_found", "note": "Set METAEDITOR_PATH to metaeditor64.exe."}


def prepare_compile(source_path: str, include_path: str | None = None) -> dict[str, Any]:
    """Build the metaeditor64.exe /compile command line for `source_path` (no execution)."""
    detected = detect_path()
    exe = detected.get("path", "metaeditor64.exe")
    log_path = f"{source_path}.log"
    args = [exe, f"/compile:{source_path}", f"/log:{log_path}"]
    if include_path:
        args.append(f"/inc:{include_path}")
    return {
        "command": args,
        "command_string": subprocess.list2cmdline(args),
        "source_path": source_path,
        "expected_log": log_path,
        "metaeditor": detected,
        "note": "This only builds the command. Run it with metaeditor_run_compile (approval required, Windows only).",
    }


def run_compile(source_path: str, include_path: str | None = None, timeout_s: int = 120) -> dict[str, Any]:
    """Run MetaEditor's compiler on `source_path`. Windows + METAEDITOR_PATH only; else gated payload."""
    if sys.platform != "win32":
        return {
            "status": UNSUPPORTED,
            "reason": REQUIRES_WINDOWS,
            "source_path": source_path,
            "note": "Compilation requires Windows + MetaEditor. Prepared command available via metaeditor_prepare_compile.",
        }
    detected = detect_path()
    exe = detected.get("path")
    if not exe or not Path(exe).exists():
        return {"status": "metaeditor_not_found", "detected": detected}

    prepared = prepare_compile(source_path, include_path)
    try:
        proc = subprocess.run(prepared["command"], capture_output=True, text=True, timeout=timeout_s)  # noqa: S603
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "timeout_s": timeout_s, "source_path": source_path}

    log_text = ""
    log_file = Path(prepared["expected_log"])
    if log_file.exists():
        log_text = _read_log_text(log_file)
    errors = parse_errors(log_text)["errors"]
    warnings = parse_warnings(log_text)["warnings"]
    return {
        "status": "compiled" if not errors else "errors",
        "return_code": proc.returncode,
        "source_path": source_path,
        "errors": errors,
        "warnings": warnings,
        "log_excerpt": log_text[-4000:],
    }


def _read_log_text(path: Path) -> str:
    for encoding in ("utf-16", "utf-8"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeError, UnicodeDecodeError):
            continue
    return path.read_text(encoding="latin-1", errors="replace")


def read_compile_log(path: str) -> dict[str, Any]:
    """Read a MetaEditor compile .log file from inside the workspace, returning its text."""
    target = resolve_within(ws.workspace_root(), path, allowed_suffixes=(".log", ".txt"), must_exist=True)
    text = _read_log_text(target)
    return {"path": path, "absolute_path": str(target), "text": text}


def _parse(log_text: str, severity: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in log_text.splitlines():
        m = _LOG_LINE.match(line.strip())
        if m and m.group("sev").lower() == severity:
            out.append(
                {
                    "file": m.group("file"),
                    "line": int(m.group("line")),
                    "column": int(m.group("col")),
                    "code": int(m.group("code")),
                    "message": m.group("msg").strip(),
                }
            )
    return out


def parse_errors(log_text: str) -> dict[str, Any]:
    """Parse `error` lines out of MetaEditor compile-log text."""
    errors = _parse(log_text, "error")
    return {"count": len(errors), "errors": errors}


def parse_warnings(log_text: str) -> dict[str, Any]:
    """Parse `warning` lines out of MetaEditor compile-log text."""
    warnings = _parse(log_text, "warning")
    return {"count": len(warnings), "warnings": warnings}


def generate_fix_plan(log_text: str, source_path: str | None = None) -> dict[str, Any]:
    """Parse errors from a compile log and turn them into a human-reviewable fix plan (no code change)."""
    errors = parse_errors(log_text)["errors"]
    return code_gen.fix_compile_error(errors, source_path=source_path)
