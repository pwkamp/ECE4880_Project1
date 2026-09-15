"""Capture reproducible repository and tool source identity."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Optional

from tests._framework.discovery import repository_root, tests_root
from tests._framework.io import load_data


def _git(repo: Path, *arguments: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _workspace_patch_hash(repo: Path, status: str, diff: str) -> str:
    digest = hashlib.sha256()
    digest.update(status.encode("utf-8"))
    digest.update(b"\0")
    digest.update(diff.encode("utf-8"))
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    for relative in sorted(item for item in (untracked or "").split("\0") if item):
        path = (repo / relative).resolve()
        try:
            path.relative_to(repo.resolve())
        except ValueError:
            continue
        if not path.is_file():
            continue
        digest.update(b"\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<unreadable>")
    return digest.hexdigest()


def collect_source_identity(repo: Path | None = None) -> Dict[str, Any]:
    repo = repo or repository_root()
    sha = _git(repo, "rev-parse", "HEAD")
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git(repo, "status", "--porcelain=v1")
    patch = _git(repo, "diff", "--binary", "HEAD") if sha else None
    dirty = bool(status) if status is not None else None
    baseline_path = tests_root() / "source_baseline.json"
    baseline = load_data(baseline_path) if baseline_path.is_file() else {}
    return {
        "repository_url": "https://github.com/pwkamp/ECE4880_Project1",
        "sha": sha,
        "branch": branch,
        "dirty": dirty,
        "patch_sha256": (
            _workspace_patch_hash(repo, status or "", patch or "")
            if sha and dirty
            else None
        ),
        "git_metadata_available": sha is not None,
        "reviewed_baseline": baseline,
    }


def collect_environment() -> Dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def collect_tool_versions(capabilities: list[str]) -> Dict[str, Optional[str]]:
    """Probe only tools relevant to the selected profile."""
    versions: Dict[str, Optional[str]] = {"python": sys.version.split()[0]}
    module_packages = {"pytest": "pytest", "fastapi": "fastapi", "jsonschema": "jsonschema"}
    command_versions = {
        "git": ["git", "--version"],
        "git-metadata": ["git", "--version"],
        "node": ["node", "--version"],
        "npm": ["npm.cmd" if os.name == "nt" else "npm", "--version"],
        "esp-idf": ["idf.py", "--version"],
        "c-compiler": ["cc", "--version"],
    }
    for capability in sorted(set(capabilities)):
        package = module_packages.get(capability)
        if package:
            try:
                versions[capability] = metadata.version(package)
            except metadata.PackageNotFoundError:
                versions[capability] = None
            continue
        command = command_versions.get(capability)
        if not command:
            continue
        if capability == "c-compiler" and shutil.which(command[0]) is None:
            selected = shutil.which("clang") or shutil.which("gcc") or shutil.which("cl")
            if selected:
                command = [selected, "--version"]
        try:
            result = subprocess.run(
                command,
                cwd=str(repository_root()),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
            output = (result.stdout or result.stderr).strip().splitlines()
            versions[capability] = output[0] if result.returncode == 0 and output else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            versions[capability] = None
    return versions
