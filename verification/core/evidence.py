"""Evidence paths and centralized secret redaction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_REDACTIONS = (
    (re.compile(r"(?i)(authorization\s*:\s*)([^\r\n]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:password|passkey|pin|token|secret|cookie)\s*[=:]\s*)([^\s,;&]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(mysql://[^:\s]+:)([^@\s]+)(@)"), r"\1[REDACTED]\3"),
    (re.compile(r"(?i)(\bMYSQL_(?:ROOT_)?PASSWORD=)([^\s]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\s-p)([^\s]+)"), r"\1[REDACTED]"),
)


def redact(value: str) -> str:
    for pattern, replacement in _REDACTIONS:
        value = pattern.sub(replacement, value)
    return value


def write_text(path: Path, value: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(value), encoding="utf-8")
    return path.as_posix()


def write_json(path: Path, value: Any) -> str:
    return write_text(path, json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
