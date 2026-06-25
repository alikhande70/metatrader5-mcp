"""Shared helpers: logging setup, JSON action-log writer, MT5 struct -> dict conversion."""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path(os.environ.get("MT5_MCP_LOG_DIR", "logs"))
LOG_LEVEL = os.environ.get("MT5_MCP_LOG_LEVEL", "INFO").upper()

_setup_lock = threading.Lock()
_write_lock = threading.Lock()
_configured = False


def _ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def get_logger(name: str = "mt5_mcp") -> logging.Logger:
    """Return a logger under the shared 'mt5_mcp' hierarchy, configuring handlers once."""
    global _configured
    with _setup_lock:
        if not _configured:
            _ensure_log_dir()
            root = logging.getLogger("mt5_mcp")
            root.setLevel(LOG_LEVEL)
            fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

            file_handler = logging.FileHandler(LOG_DIR / "mt5_mcp.log", encoding="utf-8")
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)

            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(fmt)
            root.addHandler(stream_handler)

            root.propagate = False
            _configured = True
    return logging.getLogger(name)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str = "act") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def log_action_event(event: dict[str, Any]) -> None:
    """Append one JSON line to logs/actions.log. Used for action requests and approval decisions."""
    _ensure_log_dir()
    record = {"timestamp": utcnow_iso(), **event}
    line = json.dumps(record, default=str)
    with _write_lock:
        with open(LOG_DIR / "actions.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def mt5_struct_to_dict(obj: Any) -> Any:
    """Recursively convert MT5 namedtuple results into plain dicts/lists for JSON output."""
    if obj is None:
        return None
    if hasattr(obj, "_asdict"):
        return {k: mt5_struct_to_dict(v) for k, v in obj._asdict().items()}
    if isinstance(obj, (list, tuple)):
        return [mt5_struct_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: mt5_struct_to_dict(v) for k, v in obj.items()}
    return obj
