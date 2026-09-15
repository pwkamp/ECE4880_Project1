"""Explicit UTC and monotonic clocks used in result records."""

from __future__ import annotations

import time
from datetime import datetime, timezone


def monotonic_seconds() -> float:
    return time.monotonic()


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
