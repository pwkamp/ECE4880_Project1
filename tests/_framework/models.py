"""Typed records shared by the runner and its adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TestStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"
    SKIP = "SKIP"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"
    TIMEOUT = "TIMEOUT"
    ABORTED = "ABORTED"
    INCOMPLETE = "INCOMPLETE"


class EvidenceCredit(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    SUPPORTING_ONLY = "SUPPORTING_ONLY"
    NONE = "NONE"


class LifecycleStage(str, Enum):
    DISCOVER = "DISCOVER"
    VALIDATE = "VALIDATE"
    PREFLIGHT = "PREFLIGHT"
    RESERVE = "RESERVE"
    PROVISION = "PROVISION"
    STIMULATE = "STIMULATE"
    OBSERVE = "OBSERVE"
    EVALUATE = "EVALUATE"
    TEARDOWN = "TEARDOWN"
    PUBLISH = "PUBLISH"


@dataclass(frozen=True)
class RequirementRef:
    jira: str
    uid: str


@dataclass(frozen=True)
class Profile:
    name: str
    automation: str
    evidence_credit: EvidenceCredit
    capabilities: List[str]
    optional_capabilities: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TestManifest:
    schema_version: int
    test_id: str
    name: str
    folder: Path
    entrypoint: Path
    owners: List[str]
    requirements: List[RequirementRef]
    profiles: Dict[str, Profile]
    timeout_seconds: float
    exclusive_resources: List[str]
    feasibility: str
    implementation_status: str
    raw: Dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class CapabilityResult:
    name: str
    available: bool
    detail: str


@dataclass(frozen=True)
class PlannedTest:
    manifest: TestManifest
    profile: Optional[Profile]
    status: TestStatus
    reason: str
    capabilities: List[CapabilityResult]


@dataclass
class TestResult:
    schema_version: int
    run_id: str
    test_id: str
    profile: str
    status: TestStatus
    evidence_credit: EvidenceCredit
    started_at_utc: str
    ended_at_utc: str
    duration_seconds: float
    executor: Dict[str, str]
    requirements: List[Dict[str, Any]]
    lifecycle: List[Dict[str, Any]]
    measurements: List[Dict[str, Any]] = field(default_factory=list)
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    failure: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["evidence_credit"] = self.evidence_credit.value
        return data
