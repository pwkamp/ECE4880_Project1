"""Read-only capability probing used by plan and preflight."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable, List

from tests._framework.discovery import repository_root
from tests._framework.models import CapabilityResult


MODULE_CAPABILITIES = {
    "pytest": "pytest",
    "fastapi": "fastapi",
    "jsonschema": "jsonschema",
}
COMMAND_CAPABILITIES = {
    "git": "git",
    "node": "node",
    "npm": "npm",
    "esp-idf": "idf.py",
    "c-compiler": "cc",
}


def _declared_capabilities() -> set[str]:
    raw = os.environ.get("THERMOMETER_TEST_CAPABILITIES", "")
    return {item.strip() for item in raw.replace(",", ";").split(";") if item.strip()}


def check_capability(name: str, repo: Path | None = None) -> CapabilityResult:
    repo = repo or repository_root()
    if name in _declared_capabilities():
        return CapabilityResult(name, True, "declared by THERMOMETER_TEST_CAPABILITIES")
    if name == "python":
        return CapabilityResult(name, True, sys.executable)
    if name in {"repository", "source-tree"}:
        return CapabilityResult(name, True, str(repo))
    if name == "git-metadata":
        available = (repo / ".git").exists() and shutil.which("git") is not None
        return CapabilityResult(name, available, "Git worktree available" if available else "workspace has no readable .git metadata")
    if name == "pr1-console":
        required = (repo / "package.json", repo / "src", repo / "server")
        available = all(path.exists() for path in required)
        detail = "PR #1 console tree present" if available else "PR #1 console has not been merged into this workspace"
        return CapabilityResult(name, available, detail)
    if name == "device-config":
        path = repo / "firmware" / "device_config.cmake"
        return CapabilityResult(name, path.is_file(), str(path))
    module = MODULE_CAPABILITIES.get(name)
    if module:
        available = importlib.util.find_spec(module) is not None
        return CapabilityResult(name, available, f"Python module {module}" if available else f"install Python module {module}")
    command = COMMAND_CAPABILITIES.get(name)
    if command:
        location = shutil.which(command)
        if not location and name == "c-compiler":
            location = shutil.which("clang") or shutil.which("gcc") or shutil.which("cl")
        return CapabilityResult(name, bool(location), location or f"{command} is not on PATH")
    if name.startswith("implementation:"):
        return CapabilityResult(name, False, f"{name.split(':', 1)[1]} implementation has not been added")
    return CapabilityResult(name, False, f"capability {name!r} is not configured on this host")


def check_capabilities(names: Iterable[str], repo: Path | None = None) -> List[CapabilityResult]:
    return [check_capability(name, repo) for name in names]
