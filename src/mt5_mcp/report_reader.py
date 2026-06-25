"""Strategy Tester report reader (SAFE_READ: read_strategy_report).

MT5 Strategy Tester reports are exported as HTML. This is a generic table
parser using only the standard library - it does not assume one specific
report layout, so it pairs up "Label:" / value table cells (the common MT5
convention) into a flat summary dict, and also returns the raw rows so a
caller can dig into anything the summary heuristic misses.
"""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


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


def _resolve_report_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    base = os.environ.get("MT5_MCP_REPORTS_DIR")
    if base:
        from_base = Path(base) / path
        if from_base.exists():
            return from_base
    return candidate


def read_strategy_report(path: str) -> dict[str, Any]:
    """Parse an MT5 Strategy Tester HTML report into a summary dict + raw table rows."""
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
