"""Constrained path handling for verification CLI and dashboard inputs."""

from __future__ import annotations

import re
from pathlib import Path


RUN_ID = re.compile(r"\d{4}-\d{2}-\d{2}T\d{6}Z_[0-9a-zA-Z.-]+(?:_\d+)?")
TEST_ID = re.compile(r"[A-Z][A-Z0-9-]{1,31}")


def existing_run(artifacts: Path, requested: str) -> Path | None:
    """Resolve a run by selecting an enumerated child, never by joining input."""

    root = artifacts.resolve()
    value = requested
    if requested == "latest":
        marker = root / "latest"
        if not marker.is_file():
            return None
        value = marker.read_text(encoding="utf-8").strip()
    if RUN_ID.fullmatch(value) is None or not root.is_dir():
        return None
    for candidate in root.iterdir():
        if candidate.name == value and candidate.is_dir():
            resolved = candidate.resolve()
            if resolved.parent == root:
                return resolved
    return None


def safe_test_id(value: str) -> str | None:
    """Return a path-safe test identifier or ``None``."""

    return value if TEST_ID.fullmatch(value) else None


def within(path: Path, root: Path) -> Path:
    """Return a resolved path only when it remains below the trusted root."""

    resolved = path.resolve()
    trusted = root.resolve()
    resolved.relative_to(trusted)
    return resolved
