"""Best-effort redaction before text enters the evidence bundle."""

from __future__ import annotations

import re


_RULES = (
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1<REDACTED>"),
    (re.compile(r"(?i)(passkey|password|token|secret)(\s*[:=]\s*)[^\s,;]+"), r"\1\2<REDACTED>"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<REDACTED_EMAIL>"),
    (re.compile(r"(?<!\w)\+?\d[\d(). -]{7,}\d(?!\w)"), "<REDACTED_PHONE>"),
    (re.compile(r"(?i)(mysql(?:\+\w+)?://[^:\s/]+:)[^@\s]+(@)"), r"\1<REDACTED>\2"),
)


def redact(text: str) -> str:
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text
