"""Start missing development services for hardware-in-the-loop qualification."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any


def _healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status < 400
    except Exception:
        return False


class ServiceManager:
    """Start only missing services and preserve the existing MySQL volume."""

    def __init__(self, repository: Path, evidence_dir: Path):
        self.repository = repository
        self.evidence_dir = evidence_dir
        self.processes: list[tuple[str, subprocess.Popen[Any], Any]] = []
        self.events: list[dict[str, Any]] = []

    def _start(self, name: str, command: list[str], cwd: Path, health_url: str, timeout: float = 300) -> None:
        if _healthy(health_url):
            self.events.append({"service": name, "action": "reused", "health_url": health_url})
            return
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.evidence_dir / f"{name}-service.log"
        log = log_path.open("a", encoding="utf-8")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, text=True, creationflags=flags)
        self.processes.append((name, process, log))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if _healthy(health_url):
                self.events.append({"service": name, "action": "started", "pid": process.pid, "health_url": health_url, "log": str(log_path)})
                return
            code = process.poll()
            if code is not None:
                log.flush()
                raise RuntimeError(f"{name} launcher exited with {code}; see {log_path}")
            time.sleep(1)
        raise RuntimeError(f"{name} did not become healthy within {timeout:.0f}s; see {log_path}")

    def ensure(self) -> list[dict[str, Any]]:
        # A healthy service is reused without entering ``_start``'s launch
        # branch.  Create the evidence directory up front so the startup
        # summary can still be written on a completely fresh verification
        # run where every service is already healthy.
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            shell = shutil.which("powershell") or shutil.which("pwsh")
            if not shell:
                raise RuntimeError("PowerShell is required to start Windows fixtures")
            self._start("backend", [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.repository / "backend" / "run.ps1"), "-KeepDatabase"], self.repository / "backend", "http://127.0.0.1:8000/healthz")
            self._start("frontend", [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.repository / "frontend" / "run.ps1")], self.repository / "frontend", "http://127.0.0.1:5173/api/health")
        else:
            bash = shutil.which("bash")
            if not bash:
                raise RuntimeError("bash is required to start Linux fixtures")
            self._start("backend", [bash, str(self.repository / "backend" / "run.sh"), "--keep-db"], self.repository / "backend", "http://127.0.0.1:8000/healthz")
            self._start("frontend", [bash, str(self.repository / "frontend" / "run.sh")], self.repository / "frontend", "http://127.0.0.1:5173/api/health")
        (self.evidence_dir / "service-startup.json").write_text(json.dumps(self.events, indent=2), encoding="utf-8")
        return self.events
