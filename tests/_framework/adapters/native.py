"""Common native-command adapter with evidence capture."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Mapping, Sequence

from tests._framework.clocks import utc_now_text
from tests._framework.io import atomic_write_text
from tests._framework.process_supervisor import CommandResult, run_command


class NativeToolFailure(AssertionError):
    pass


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "command"


class NativeToolAdapter:
    def __init__(self, repository: Path, attachments: Path, events_path: Path) -> None:
        self.repository = repository
        self.attachments = attachments
        self.events_path = events_path
        self.attachments.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        name: str,
        command: Sequence[str],
        timeout_seconds: float,
        environment: Mapping[str, str] | None = None,
    ) -> CommandResult:
        safe_name = _safe_name(name)
        result = run_command(command, self.repository, timeout_seconds, environment)
        atomic_write_text(self.attachments / f"{safe_name}.stdout.log", result.stdout)
        atomic_write_text(self.attachments / f"{safe_name}.stderr.log", result.stderr)
        event = {
            "schema_version": 1,
            "type": "native_tool",
            "captured_at_utc": utc_now_text(),
            "name": name,
            "command": list(command),
            "returncode": result.returncode,
            "duration_seconds": result.duration_seconds,
            "timed_out": result.timed_out,
        }
        with self.events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event) + "\n")
        if result.timed_out:
            raise TimeoutError(f"{name} exceeded {timeout_seconds:.1f} seconds")
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            raise NativeToolFailure(f"{name} failed: {detail[-1000:]}")
        return result
