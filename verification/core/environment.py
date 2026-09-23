"""Reproducible run metadata collection."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .catalog import catalog_hash


def _version(command: list[str]) -> str | None:
    executable = shutil.which(command[0])
    if executable:
        command = [executable, *command[1:]]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0] if result.returncode == 0 and text else None


def _git(repository: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=repository, capture_output=True, text=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def collect(repository: Path, verification_root: Path, profile: str, run_id: str) -> dict[str, object]:
    dirty = _git(repository, "status", "--porcelain")
    protocol_path = repository / "protocol" / "thermometer_protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    firmware_sources = sorted((repository / "firmware").glob("**/*.[ch]"))
    firmware_digest = hashlib.sha256()
    for source in firmware_sources:
        firmware_digest.update(source.relative_to(repository).as_posix().encode())
        firmware_digest.update(source.read_bytes())
    docker_version = _version(["docker", "--version"])
    mysql_version = _version(["mysql", "--version"])
    if mysql_version is None and docker_version and profile != "software":
        image_id = _version(["docker", "image", "inspect", "mysql:8.4", "--format={{.Id}}"])
        mysql_version = f"mysql:8.4 container image ({image_id or 'image not yet available'})"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "profile": profile,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "operating_system": platform.platform(),
        "git_sha": _git(repository, "rev-parse", "HEAD"),
        "git_state": "dirty" if dirty else "clean",
        "python_version": sys.version.split()[0],
        "node_version": _version(["node", "--version"]),
        "npm_version": _version(["npm", "--version"]),
        "docker_version": docker_version,
        "mysql_version": mysql_version,
        "esp_idf_version": _version(["idf.py", "--version"]),
        "protocol_version": protocol.get("protocol", {}).get("version"),
        "firmware_source_sha256": firmware_digest.hexdigest(),
        "requirements_catalog_sha256": catalog_hash(verification_root / "requirements.yaml"),
        "test_catalog_sha256": catalog_hash(verification_root / "tests.yaml"),
        "setup_groups_catalog_sha256": catalog_hash(verification_root / "setup_groups.yaml"),
    }
