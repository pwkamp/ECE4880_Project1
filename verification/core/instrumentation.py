"""Small, dependency-free qualification instrumentation helpers.

These helpers keep timing and evidence formats consistent without coupling
production code to the verification framework.
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from .evidence import redact, write_json, write_text


T = TypeVar("T")


@dataclass(frozen=True)
class TimedValue:
    value: Any
    duration_ms: float


def measure(call: Callable[[], T]) -> TimedValue:
    """Execute *call* and measure it with the required monotonic clock."""

    started = time.perf_counter_ns()
    value = call()
    return TimedValue(value, (time.perf_counter_ns() - started) / 1_000_000)


class TimestampedLog:
    """Append redacted, UTC-correlated lines for backend/serial captures."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, message: str, *, monotonic_ns: int | None = None) -> None:
        marker = monotonic_ns if monotonic_ns is not None else time.perf_counter_ns()
        utc = datetime.now(timezone.utc).isoformat()
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(redact(f"{utc} monotonic_ns={marker} {message}\n"))


class CapturedHttpClient:
    """urllib wrapper that writes a redacted JSON record for each exchange."""

    def __init__(self, evidence_directory: Path) -> None:
        self.evidence_directory = evidence_directory
        self.sequence = 0

    def request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10,
    ) -> tuple[int, bytes]:
        request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
        started = time.perf_counter_ns()
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read()
            status = response.status
        duration_ms = (time.perf_counter_ns() - started) / 1_000_000
        self.sequence += 1
        write_json(
            self.evidence_directory / f"http-{self.sequence:03d}.json",
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "method": method,
                "url": url,
                "request_headers": headers or {},
                "request_body": body.decode("utf-8", errors="replace") if body else None,
                "response_status": status,
                "response_body": response_body.decode("utf-8", errors="replace"),
                "duration_ms": duration_ms,
            },
        )
        return status, response_body


def write_database_capture(
    directory: Path,
    *,
    query: str,
    columns: list[str],
    before: Iterable[Iterable[Any]],
    after: Iterable[Iterable[Any]],
    explain: Any | None = None,
) -> list[str]:
    """Write the standard SQL, before/after CSV, and optional EXPLAIN evidence."""

    paths: list[str] = []
    paths.append(write_text(directory / "query.sql", query + "\n"))
    for name, rows in (("database_before.csv", before), ("database_after.csv", after)):
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(columns)
        writer.writerows(rows)
        paths.append(write_text(directory / name, buffer.getvalue()))
    if explain is not None:
        paths.append(write_json(directory / "explain.json", explain))
    return paths

