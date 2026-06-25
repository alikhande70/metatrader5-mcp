"""Read-only access to MT5 terminal/expert log files (SAFE_READ: read_log).

MT5 writes daily log files named YYYYMMDD.log under <data_path>/Logs (terminal
logs) and <data_path>/MQL5/Logs (Expert Advisor logs). This module only reads
those files - it never writes to the terminal or its data folder.
"""

from __future__ import annotations

import os
from datetime import date as date_cls
from pathlib import Path

from . import mt5_bridge

# MT5 log files have historically been UTF-16 with a BOM; fall back gracefully.
_ENCODING_CANDIDATES = ("utf-16", "utf-8", "latin-1")


def _resolve_log_dir(kind: str = "terminal", log_dir: str | None = None) -> Path:
    if log_dir:
        return Path(log_dir)
    override = os.environ.get("MT5_MCP_LOG_SOURCE_DIR")
    if override:
        return Path(override)

    terminal_info = mt5_bridge.get_terminal_info()
    data_path = terminal_info.get("data_path")
    if not data_path:
        raise FileNotFoundError("MT5 terminal_info() did not return a data_path; cannot locate logs.")
    base = Path(data_path)
    return base / "MQL5" / "Logs" if kind == "experts" else base / "Logs"


def _read_text(path: Path) -> str:
    last_error: Exception | None = None
    for encoding in _ENCODING_CANDIDATES:
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeError, LookupError) as exc:
            last_error = exc
    raise RuntimeError(f"Could not decode log file {path} with any known encoding") from last_error


def list_available_logs(kind: str = "terminal", log_dir: str | None = None) -> list[str]:
    directory = _resolve_log_dir(kind, log_dir)
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.log"))


def read_log(date: str | None = None, lines: int = 200, kind: str = "terminal", log_dir: str | None = None) -> dict:
    """Return the last `lines` lines of the terminal/expert log for `date` (YYYYMMDD, default today)."""
    directory = _resolve_log_dir(kind, log_dir)
    date = date or date_cls.today().strftime("%Y%m%d")
    file_path = directory / f"{date}.log"

    if not file_path.exists():
        available = list_available_logs(kind, log_dir)
        hint = f"Available dates: {available[-10:]}" if available else "No log files found in this directory."
        raise FileNotFoundError(
            f"Log file not found: {file_path}. Looked in log directory '{directory}' for "
            f"kind='{kind}' logs. {hint}"
        )

    all_lines = _read_text(file_path).splitlines()
    tail = all_lines[-lines:] if lines > 0 else all_lines

    return {
        "kind": kind,
        "date": date,
        "path": str(file_path),
        "total_lines": len(all_lines),
        "returned_lines": len(tail),
        "lines": tail,
    }
