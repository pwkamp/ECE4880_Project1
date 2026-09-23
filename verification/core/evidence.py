"""Evidence paths and centralized secret redaction."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from .paths import within


_REDACTIONS = (
    (re.compile(r"(?i)(authorization\s*:\s*)([^\r\n]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:password|passkey|pin|token|secret|cookie)\s*[=:]\s*)([^\s,;&]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(mysql://[^:\s]+:)([^@\s]+)(@)"), r"\1[REDACTED]\3"),
    (re.compile(r"(?i)(\bMYSQL_(?:ROOT_)?PASSWORD=)([^\s]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\s-p)([^\s]+)"), r"\1[REDACTED]"),
)

_REPOSITORY = Path(__file__).resolve().parents[2]
_OUTPUT_ROOTS = (
    _REPOSITORY / "artifacts" / "verification",
    _REPOSITORY / "verification" / "dashboard",
    Path(tempfile.gettempdir()),
)


def safe_output_path(path: Path) -> Path:
    for root in _OUTPUT_ROOTS:
        try:
            return within(path, root)
        except ValueError:
            continue
    raise ValueError(f"verification output path is outside approved roots: {path}")


def redact(value: str) -> str:
    for pattern, replacement in _REDACTIONS:
        value = pattern.sub(replacement, value)
    return value


def write_text(path: Path, value: str) -> str:
    destination = safe_output_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(redact(value), encoding="utf-8")
    return destination.as_posix()


def write_json(path: Path, value: Any) -> str:
    return write_text(path, json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
