"""Discover and decode consolidated test manifests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List

from tests._framework.io import load_data
from tests._framework.models import EvidenceCredit, Profile, RequirementRef, TestManifest


FOLDER_PATTERN = re.compile(r"^[a-z]{2,4}_\d{3}_[a-z0-9_]+$")


def tests_root() -> Path:
    return Path(__file__).resolve().parents[1]


def repository_root() -> Path:
    return tests_root().parent


def _decode_manifest(folder: Path, raw: Dict[str, object]) -> TestManifest:
    profiles: Dict[str, Profile] = {}
    for name, profile_value in dict(raw.get("profiles", {})).items():
        profile = dict(profile_value)
        profiles[name] = Profile(
            name=name,
            automation=str(profile.get("automation", "automated")),
            evidence_credit=EvidenceCredit(str(profile.get("evidence_credit", "NONE"))),
            capabilities=list(profile.get("capabilities", [])),
            optional_capabilities=list(profile.get("optional_capabilities", [])),
        )
    requirements = [
        RequirementRef(jira=str(item["jira"]), uid=str(item["uid"]))
        for item in list(raw.get("requirements", []))
    ]
    entrypoint_name = str(raw.get("entrypoint", ""))
    return TestManifest(
        schema_version=int(raw.get("schema_version", 0)),
        test_id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        folder=folder,
        entrypoint=folder / entrypoint_name,
        owners=list(raw.get("owners", [])),
        requirements=requirements,
        profiles=profiles,
        timeout_seconds=float(raw.get("timeout_seconds", 0)),
        exclusive_resources=list(raw.get("exclusive_resources", [])),
        feasibility=str(raw.get("current_feasibility", "")),
        implementation_status=str(dict(raw.get("implementation", {})).get("status", "placeholder")),
        raw=raw,
    )


def discover(root: Path | None = None) -> List[TestManifest]:
    root = root or tests_root()
    manifests: List[TestManifest] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not FOLDER_PATTERN.fullmatch(folder.name):
            continue
        manifest_path = folder / "test.yaml"
        if not manifest_path.is_file():
            continue
        raw = load_data(manifest_path)
        if not isinstance(raw, dict):
            raise ValueError(f"{manifest_path} must contain an object")
        manifests.append(_decode_manifest(folder, raw))
    return manifests


def by_id(manifests: Iterable[TestManifest]) -> Dict[str, TestManifest]:
    return {manifest.test_id: manifest for manifest in manifests}
