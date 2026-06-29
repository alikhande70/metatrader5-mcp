"""Shared filesystem-confinement helper.

Several tools read or write files from disk and must never become a way to reach
arbitrary paths. Every such tool resolves the caller-supplied path strictly inside a
configured base directory via :func:`resolve_within`, which rejects:

  - disallowed file extensions,
  - absolute paths that point outside the base directory, and
  - ``..`` traversal that escapes the base directory.

report_reader, log_reader, the MQL5 workspace/file tools, drafts and backups all share
this one implementation so the confinement rule is defined and tested in exactly one
place.
"""

from __future__ import annotations

import os
from pathlib import Path


class PathConfinementError(ValueError):
    """Raised when a path escapes its allowed base directory or has a disallowed suffix."""


def env_base_dir(env_var: str, default_dirname: str) -> Path:
    """Resolve a base directory from ``env_var`` or fall back to ``default_dirname`` under cwd."""
    raw = os.environ.get(env_var)
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.cwd() / default_dirname).resolve()


def resolve_within(
    base_dir: Path,
    path: str,
    *,
    allowed_suffixes: tuple[str, ...] | None = None,
    must_exist: bool = False,
) -> Path:
    """Resolve ``path`` strictly inside ``base_dir``.

    ``allowed_suffixes`` (lowercased, with leading dots) restricts which file
    extensions are accepted; ``None`` allows any. Raises :class:`PathConfinementError`
    on a disallowed suffix or any escape from ``base_dir``; raises
    :class:`FileNotFoundError` when ``must_exist`` is set and the target is missing.
    """
    base_dir = base_dir.resolve()

    if allowed_suffixes is not None:
        suffix = Path(path).suffix.lower()
        if suffix not in allowed_suffixes:
            raise PathConfinementError(
                f"Path '{path}' has suffix '{suffix or '<none>'}', which is not allowed here. "
                f"Allowed: {', '.join(allowed_suffixes)} (resolved under {base_dir})."
            )

    # If `path` is absolute it wins the join; the containment check below is what
    # actually enforces safety in every case.
    candidate = (base_dir / path).resolve()

    if candidate != base_dir and not candidate.is_relative_to(base_dir):
        raise PathConfinementError(
            f"Path '{path}' resolves outside the allowed directory ({base_dir}). "
            "Absolute paths elsewhere and '..' traversal that escapes the base are rejected."
        )

    if must_exist and not candidate.exists():
        raise FileNotFoundError(f"Path not found inside {base_dir}: {candidate}")

    return candidate
