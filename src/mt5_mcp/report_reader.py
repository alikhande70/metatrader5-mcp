"""Strategy Tester report reader (SAFE_READ: read_strategy_report).

MT5 Strategy Tester reports are exported as HTML. This is a generic table
parser using only the standard library - it does not assume one specific
report layout, so it pairs up "Label:" / value table cells (the common MT5
convention) into a flat summary dict, and also returns the raw rows so a
caller can dig into anything the summary heuristic misses.

Path safety: because this is a SAFE_READ tool, it must only ever read
Strategy Tester reports - never arbitrary files. Every requested path is
confined to the reports directory (MT5_MCP_REPORTS_DIR, or the documented
default `reports/` under the runtime working directory). Absolute paths and
`..` traversal that escape that directory are rejected, and only .html/.htm
files are allowed.
"""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Default reports directory used when MT5_MCP_REPORTS_DIR is not set. It lives
# under the runtime working directory so the SAFE_READ tool has a bounded,
# documented location to read from rather than the whole filesystem.
DEFAULT_REPORTS_DIRNAME = "reports"

ALLOWED_REPORT_SUFFIXES = (".html", ".htm")


class ReportPathError(ValueError):
    """Raised when a report path escapes the allowed reports directory or has a disallowed extension."""


class _TableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._current_cell is not None and self._current_row is not None:
            text = re.sub(r"\s+", " ", "".join(self._current_cell)).strip()
            self._current_row.append(text)
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if any(self._current_row):
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)


def _rows_from_html(html_text: str) -> list[list[str]]:
    parser = _TableHTMLParser()
    parser.feed(html_text)
    return parser.rows


def _summary_from_rows(rows: list[list[str]]) -> dict[str, str]:
    """Pair each 'Label:' cell with the cell right after it, across all rows."""
    summary: dict[str, str] = {}
    for row in rows:
        i = 0
        while i < len(row):
            cell = row[i]
            if cell.endswith(":") and i + 1 < len(row):
                label = cell.rstrip(":").strip()
                value = row[i + 1].strip()
                if label and value:
                    summary[label] = value
                i += 2
            else:
                i += 1
    return summary


def _reports_base_dir() -> Path:
    """Resolved base directory that all reports must live under."""
    base = os.environ.get("MT5_MCP_REPORTS_DIR")
    if base:
        return Path(base).expanduser().resolve()
    return (Path.cwd() / DEFAULT_REPORTS_DIRNAME).resolve()


def _resolve_report_path(path: str) -> Path:
    """Resolve `path` strictly inside the reports base directory.

    Rejects disallowed extensions, absolute paths that point outside the base
    directory, and any `..` traversal that escapes it.
    """
    if Path(path).suffix.lower() not in ALLOWED_REPORT_SUFFIXES:
        raise ReportPathError(
            f"read_strategy_report only accepts {'/'.join(ALLOWED_REPORT_SUFFIXES)} files, got '{path}'."
        )

    base_dir = _reports_base_dir()
    # Joining keeps relative paths under base_dir; if `path` is absolute it wins
    # the join, so the containment check below is what actually enforces safety.
    candidate = (base_dir / path).resolve()

    if not candidate.is_relative_to(base_dir):
        raise ReportPathError(
            f"Report path '{path}' resolves outside the allowed reports directory ({base_dir}). "
            "Use a path inside MT5_MCP_REPORTS_DIR (or the default 'reports/' directory)."
        )
    return candidate


def read_strategy_report(path: str) -> dict[str, Any]:
    """Parse an MT5 Strategy Tester HTML report into a summary dict + raw table rows.

    `path` is always resolved inside the reports directory (MT5_MCP_REPORTS_DIR
    or the default `reports/`); arbitrary absolute paths and `..` traversal are
    rejected, and only .html/.htm files are allowed.
    """
    report_path = _resolve_report_path(path)
    if not report_path.exists():
        raise FileNotFoundError(f"Strategy Tester report not found: {report_path}")

    try:
        html_text = report_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        html_text = report_path.read_text(encoding="utf-16")

    rows = _rows_from_html(html_text)
    summary = _summary_from_rows(rows)

    return {
        "path": str(report_path),
        "summary": summary,
        "raw_rows": rows,
    }
