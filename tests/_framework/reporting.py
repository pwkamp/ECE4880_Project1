"""Read and integrity-check an already published run."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List

from tests._framework.io import load_data


def verify_run(run_path: Path) -> List[str]:
    errors: List[str] = []
    manifest_path = run_path / "evidence-manifest.json"
    if not manifest_path.is_file():
        return ["run evidence-manifest.json is missing"]
    manifest = load_data(manifest_path)
    run_record_path = run_path / "run.json"
    if run_record_path.is_file():
        run_record = load_data(run_record_path)
        expected_manifest_hash = run_record.get("evidence_manifest_sha256")
        actual_manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if expected_manifest_hash != actual_manifest_hash:
            errors.append("run record does not match the evidence manifest hash")
    for record in manifest.get("files", []):
        path = run_path / record["path"]
        if not path.is_file():
            errors.append(f"missing evidence file {record['path']}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            errors.append(f"evidence hash mismatch for {record['path']}")
        if path.stat().st_size != record["size_bytes"]:
            errors.append(f"evidence size mismatch for {record['path']}")
    return errors


def load_run(run_path: Path) -> Dict[str, Any]:
    return load_data(run_path / "run.json")
