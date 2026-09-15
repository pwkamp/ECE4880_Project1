"""Catalog, frozen-requirement, and legacy-test mapping validation."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from tests._framework.discovery import discover, repository_root, tests_root
from tests._framework.io import load_data
from tests._framework.models import TestManifest


TEST_ID_PATTERN = re.compile(r"^[A-Z]{2,4}-\d{3}$")
JIRA_PATTERN = re.compile(r"^SCRUM-\d+$")
EXPECTED_LEVEL_COUNTS = {"Project": 5, "HLR": 18, "MLR": 76, "LLR": 156}
SCHEMA_FILES = (
    "requirements.schema.json",
    "test_manifest.schema.json",
    "result.schema.json",
)


@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    test_count: int = 0
    requirement_count: int = 0
    legacy_test_count: int = 0

    @property
    def valid(self) -> bool:
        return not self.errors


def _content_hash(requirement: Mapping[str, object]) -> str:
    payload = {key: value for key, value in requirement.items() if key != "content_sha256"}
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_requirement_lock(report: ValidationReport, path: Path) -> Dict[str, Mapping[str, object]]:
    try:
        lock = load_data(path)
    except Exception as error:
        report.errors.append(f"cannot load requirement lock: {error}")
        return {}
    requirements = list(lock.get("requirements", []))
    report.requirement_count = len(requirements)
    if len(requirements) != 255:
        report.errors.append(f"expected 255 locked requirements, found {len(requirements)}")
    counts = {level: 0 for level in EXPECTED_LEVEL_COUNTS}
    by_uid: Dict[str, Mapping[str, object]] = {}
    by_jira: Dict[str, str] = {}
    for requirement in requirements:
        uid = str(requirement.get("uid", ""))
        jira = str(requirement.get("jira", ""))
        level = str(requirement.get("level", ""))
        if uid in by_uid:
            report.errors.append(f"duplicate requirement UID {uid}")
        if jira in by_jira:
            report.errors.append(f"duplicate Jira key {jira}")
        if not JIRA_PATTERN.fullmatch(jira):
            report.errors.append(f"invalid Jira key {jira!r}")
        if level not in counts:
            report.errors.append(f"invalid requirement level {level!r} for {uid}")
        else:
            counts[level] += 1
        expected_hash = _content_hash(requirement)
        if requirement.get("content_sha256") != expected_hash:
            report.errors.append(f"content hash mismatch for {uid}")
        by_uid[uid] = requirement
        by_jira[jira] = uid
    if counts != EXPECTED_LEVEL_COUNTS:
        report.errors.append(f"requirement level counts are {counts}, expected {EXPECTED_LEVEL_COUNTS}")
    expected_baseline = hashlib.sha256(
        json.dumps(requirements, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if lock.get("baseline_sha256") != expected_baseline:
        report.errors.append("requirements baseline hash does not match its locked records")
    return by_uid


def _matrix_mapping(path: Path, report: ValidationReport) -> Dict[str, List[Tuple[str, str]]]:
    mapping: Dict[str, List[Tuple[str, str]]] = {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except Exception as error:
        report.errors.append(f"cannot load frozen test matrix: {error}")
        return mapping
    if len(rows) != 56:
        report.errors.append(f"expected 56 matrix rows, found {len(rows)}")
    for row in rows:
        test_id = row.get("Test ID", "").strip()
        uids = [value.strip() for value in row.get("Requirements Covered", "").split(";") if value.strip()]
        jira_keys = [value.strip() for value in row.get("Jira Issues", "").split(";") if value.strip()]
        if len(uids) != len(jira_keys):
            report.errors.append(f"matrix row {test_id} has mismatched UID/Jira lists")
        mapping[test_id] = list(zip(uids, jira_keys))
    return mapping


def discover_unittest_cases(test_directory: Path) -> List[str]:
    cases: List[str] = []
    repo = repository_root()
    for path in sorted(test_directory.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        try:
            relative = path.relative_to(repo).as_posix()
        except ValueError:
            relative = path.as_posix()
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name.startswith("test_"):
                        cases.append(f"{relative}::{node.name}::{member.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                cases.append(f"{relative}::{node.name}")
    return cases


def _validate_legacy_mapping(report: ValidationReport, path: Path) -> None:
    try:
        mapping = load_data(path)
    except Exception as error:
        report.errors.append(f"cannot load existing Python test mapping: {error}")
        return
    mapped_cases: List[str] = []
    for owner, cases in dict(mapping.get("owners", {})).items():
        if not TEST_ID_PATTERN.fullmatch(owner):
            report.errors.append(f"invalid owner {owner!r} in existing Python test mapping")
        mapped_cases.extend(cases)
    if len(mapped_cases) != len(set(mapped_cases)):
        report.errors.append("an existing Python test is mapped to more than one consolidated owner")
    discovered = discover_unittest_cases(repository_root() / "backend" / "pc_client" / "tests")
    report.legacy_test_count = len(discovered)
    missing = sorted(set(discovered) - set(mapped_cases))
    unknown = sorted(set(mapped_cases) - set(discovered))
    if missing:
        report.errors.append(f"{len(missing)} existing Python tests are unmapped: {', '.join(missing[:3])}")
    if unknown:
        report.errors.append(f"{len(unknown)} mapped Python tests no longer exist: {', '.join(unknown[:3])}")
    expected = int(mapping.get("expected_test_count", 0))
    if expected != len(discovered):
        report.errors.append(f"existing Python test count changed from {expected} to {len(discovered)}")


def _validate_pr1_mapping(report: ValidationReport, path: Path) -> None:
    try:
        mapping = load_data(path)
    except Exception as error:
        report.errors.append(f"cannot load PR #1 Vitest mapping: {error}")
        return
    files = [
        file_name
        for values in dict(mapping.get("owners", {})).values()
        for file_name in values
    ]
    if len(files) != len(set(files)):
        report.errors.append("a PR #1 Vitest file has more than one primary owner")
    reviewed_files = [
        file_name
        for file_name in files
        if not file_name.startswith("tests/_shared/")
    ]
    expected = int(mapping.get("reviewed_pr_test_file_count", 0))
    if len(reviewed_files) != expected:
        report.errors.append(
            f"PR #1 mapping contains {len(reviewed_files)} reviewed test files; expected {expected}"
        )


def validate_catalog(root: Path | None = None) -> ValidationReport:
    root = root or tests_root()
    report = ValidationReport()
    input_baseline: Dict[str, Any] = {}
    try:
        input_baseline = load_data(root / "input_baseline.json")
        matrix_digest = hashlib.sha256(
            (root / "test_matrix.lock.csv").read_bytes()
        ).hexdigest()
        if matrix_digest != input_baseline["test_matrix"]["sha256"]:
            report.errors.append(
                "frozen test matrix hash changed; review and update the input baseline"
            )
    except Exception as error:
        report.errors.append(f"cannot validate input_baseline.json: {error}")
    schemas: Dict[str, Mapping[str, object]] = {}
    for filename in SCHEMA_FILES:
        try:
            schema = load_data(root / filename)
            if not isinstance(schema, dict) or "$schema" not in schema:
                report.errors.append(f"{filename} is not a JSON Schema document")
            else:
                schemas[filename] = schema
        except Exception as error:
            report.errors.append(f"cannot load {filename}: {error}")
    requirements = _validate_requirement_lock(report, root / "requirements.lock.json")
    if requirements and input_baseline:
        locked_baseline = load_data(root / "requirements.lock.json")["baseline_sha256"]
        expected_baseline = input_baseline["jira_requirements"][
            "requirement_content_baseline_sha256"
        ]
        if locked_baseline != expected_baseline:
            report.errors.append(
                "Jira requirement baseline changed; procedures require review"
            )
    matrix = _matrix_mapping(root / "test_matrix.lock.csv", report)
    try:
        manifests = discover(root)
    except Exception as error:
        report.errors.append(f"test discovery failed: {error}")
        return report
    report.test_count = len(manifests)
    if len(manifests) != 56:
        report.errors.append(f"expected 56 test folders, found {len(manifests)}")
    seen_ids: set[str] = set()
    owners: Dict[str, str] = {}
    for manifest in manifests:
        if manifest.test_id in seen_ids:
            report.errors.append(f"duplicate test ID {manifest.test_id}")
        seen_ids.add(manifest.test_id)
        if not TEST_ID_PATTERN.fullmatch(manifest.test_id):
            report.errors.append(f"invalid test ID {manifest.test_id!r}")
        if manifest.schema_version != 1:
            report.errors.append(f"{manifest.test_id} uses unsupported manifest schema {manifest.schema_version}")
        if not (manifest.folder / "README.md").is_file():
            report.errors.append(f"{manifest.test_id} is missing README.md")
        if not manifest.entrypoint.is_file() or manifest.entrypoint.parent != manifest.folder:
            report.errors.append(f"{manifest.test_id} has a missing or unsafe entrypoint")
        if manifest.timeout_seconds <= 0:
            report.errors.append(f"{manifest.test_id} timeout must be positive")
        if not manifest.profiles:
            report.errors.append(f"{manifest.test_id} has no execution profiles")
        actual = [(item.uid, item.jira) for item in manifest.requirements]
        expected = matrix.get(manifest.test_id)
        if expected is None:
            report.errors.append(f"{manifest.test_id} is absent from the frozen matrix")
        elif actual != expected:
            report.errors.append(f"{manifest.test_id} requirement mapping differs from the frozen matrix")
        for item in manifest.requirements:
            locked = requirements.get(item.uid)
            if locked is None:
                report.errors.append(f"{manifest.test_id} references unknown UID {item.uid}")
                continue
            if locked.get("jira") != item.jira:
                report.errors.append(f"{item.uid} Jira key differs from the requirement lock")
            if item.uid in owners:
                report.errors.append(f"{item.uid} is primarily owned by both {owners[item.uid]} and {manifest.test_id}")
            owners[item.uid] = manifest.test_id
            if locked.get("primary_test") != manifest.test_id:
                report.errors.append(f"{item.uid} owner differs from the Jira baseline lock")
    missing_tests = sorted(set(matrix) - seen_ids)
    if missing_tests:
        report.errors.append(f"matrix tests have no folder: {', '.join(missing_tests)}")
    if len(owners) != 255:
        report.errors.append(f"expected 255 unique primary owners, found {len(owners)}")
    _validate_legacy_mapping(report, root / "_shared" / "existing_python_tests.json")
    _validate_pr1_mapping(report, root / "_shared" / "pr1_vitest_suites.json")
    try:
        import jsonschema  # type: ignore
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        try:
            for schema in schemas.values():
                jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(
                load_data(root / "requirements.lock.json"),
                schemas["requirements.schema.json"],
            )
            manifest_schema = schemas["test_manifest.schema.json"]
            for manifest in manifests:
                jsonschema.validate(
                    load_data(manifest.folder / "test.yaml"), manifest_schema
                )
        except Exception as error:
            report.errors.append(f"JSON Schema validation failed: {error}")
    return report
