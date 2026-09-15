"""Bounded subprocess execution with group termination and redacted logs."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

from tests._framework.redaction import redact


@dataclass(frozen=True)
class CommandResult:
    command: Sequence[str]
    returncode: Optional[int]
    duration_seconds: float
    timed_out: bool
    stdout: str
    stderr: str


def run_command(
    command: Sequence[str],
    cwd: Path,
    timeout_seconds: float,
    environment: Mapping[str, str] | None = None,
) -> CommandResult:
    env = os.environ.copy()
    if environment:
        env.update(environment)
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    start = time.monotonic()
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
    return CommandResult(
        command=tuple(command),
        returncode=process.returncode,
        duration_seconds=time.monotonic() - start,
        timed_out=timed_out,
        stdout=redact(stdout),
        stderr=redact(stderr),
    )
