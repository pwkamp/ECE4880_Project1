"""Immutable run publication and attachment integrity records."""

from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List

from tests._framework.clocks import utc_now_text
from tests._framework.io import atomic_write_json, atomic_write_text
from tests._framework.models import TestResult


class EvidenceError(RuntimeError):
    pass


def file_record(path: Path, relative_to: Path) -> Dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "path": path.relative_to(relative_to).as_posix(),
        "sha256": digest.hexdigest(),
        "size_bytes": path.stat().st_size,
        "mime_type": mime_type,
        "captured_at_utc": utc_now_text(),
    }


def render_result_markdown(result: Dict[str, Any]) -> str:
    lines = [
        f"# {result['test_id']} result",
        "",
        f"- Status: `{result['status']}`",
        f"- Evidence credit: `{result['evidence_credit']}`",
        f"- Profile: `{result['profile']}`",
        f"- Run: `{result['run_id']}`",
        f"- Started: `{result['started_at_utc']}`",
        f"- Ended: `{result['ended_at_utc']}`",
        f"- Monotonic duration: `{result['duration_seconds']:.3f} s`",
        "",
        "## Requirements",
        "",
    ]
    for requirement in result["requirements"]:
        lines.append(
            f"- {requirement['uid']} ({requirement['jira']}): "
            f"`{requirement['status']}` / `{requirement['credit']}`"
        )
    lines.extend(["", "## Evidence", ""])
    if result.get("artifacts"):
        for artifact in result["artifacts"]:
            lines.append(f"- `{artifact['path']}` - SHA-256 `{artifact['sha256']}`")
    else:
        lines.append("- No attachments were produced.")
    if result.get("failure"):
        lines.extend(["", "## Failure", "", f"`{result['failure'].get('kind')}`: {result['failure'].get('message')}"])
    if result.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result["warnings"])
    return "\n".join(lines) + "\n"


class EvidenceRun:
    def __init__(self, results_root: Path, run_id: str) -> None:
        self.results_root = results_root
        self.run_id = run_id
        self.final_path = results_root / run_id
        self.temporary_path = results_root / f".{run_id}.tmp"
        if self.final_path.exists() or self.temporary_path.exists():
            raise EvidenceError(f"run {run_id!r} already exists")
        self.temporary_path.mkdir(parents=True)
        self.results: List[Dict[str, Any]] = []

    def test_path(self, test_id: str) -> Path:
        path = self.temporary_path / "tests" / test_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_result(self, result: TestResult) -> None:
        test_path = self.test_path(result.test_id)
        attachments = test_path / "attachments"
        artifacts = []
        if attachments.is_dir():
            artifacts = [file_record(path, test_path) for path in sorted(attachments.rglob("*")) if path.is_file()]
        result.artifacts = artifacts
        data = result.to_dict()
        try:
            import jsonschema  # type: ignore
        except ImportError as error:
            raise EvidenceError(
                "jsonschema is required to publish qualified test evidence"
            ) from error
        schema_path = Path(__file__).resolve().parents[1] / "result.schema.json"
        try:
            jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
        except Exception as error:
            raise EvidenceError(f"result schema validation failed: {error}") from error
        atomic_write_json(test_path / "evidence-manifest.json", {"schema_version": 1, "artifacts": artifacts})
        atomic_write_json(test_path / "result.json", data)
        atomic_write_text(test_path / "result.md", render_result_markdown(data))
        self.results.append(data)

    def finalize(self, run_record: Dict[str, Any]) -> Path:
        run_record = dict(run_record)
        run_record["results"] = [
            {"test_id": item["test_id"], "status": item["status"], "evidence_credit": item["evidence_credit"]}
            for item in self.results
        ]
        counts: Dict[str, int] = {}
        for item in self.results:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        run_record["aggregate_counts"] = counts
        manifest_files = [
            file_record(path, self.temporary_path)
            for path in sorted((self.temporary_path / "tests").rglob("*"))
            if path.is_file()
        ]
        overall_manifest_path = self.temporary_path / "evidence-manifest.json"
        atomic_write_json(
            overall_manifest_path,
            {"schema_version": 1, "files": manifest_files},
        )
        run_record["evidence_manifest_sha256"] = hashlib.sha256(
            overall_manifest_path.read_bytes()
        ).hexdigest()
        atomic_write_json(self.temporary_path / "run.json", run_record)
        summary_lines = [f"# Test run {self.run_id}", "", "| Test | Status | Credit |", "|---|---|---|"]
        summary_lines.extend(
            f"| {item['test_id']} | {item['status']} | {item['evidence_credit']} |" for item in self.results
        )
        atomic_write_text(self.temporary_path / "summary.md", "\n".join(summary_lines) + "\n")
        with (self.temporary_path / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["test_id", "status", "evidence_credit"])
            writer.writeheader()
            for item in self.results:
                writer.writerow({key: item[key] for key in writer.fieldnames})
        os.replace(self.temporary_path, self.final_path)
        return self.final_path

    def preserve_incomplete(self, message: str) -> Path:
        atomic_write_json(
            self.temporary_path / "run.json",
            {"schema_version": 1, "run_id": self.run_id, "status": "INCOMPLETE", "message": message},
        )
        os.replace(self.temporary_path, self.final_path)
        return self.final_path
