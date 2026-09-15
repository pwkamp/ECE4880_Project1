"""Single-test lifecycle execution and immutable evidence publication."""

from __future__ import annotations

import getpass
import json
import os
import platform
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from tests import RUNNER_VERSION
from tests._framework.clocks import monotonic_seconds, utc_now_text
from tests._framework.discovery import repository_root, tests_root
from tests._framework.evidence import EvidenceRun
from tests._framework.io import atomic_write_json, atomic_write_text
from tests._framework.models import EvidenceCredit, LifecycleStage, PlannedTest, TestResult, TestStatus
from tests._framework.process_supervisor import run_command
from tests._framework.resource_locks import ResourceBusyError, ResourceLockSet
from tests._framework.source import (
    collect_environment,
    collect_source_identity,
    collect_tool_versions,
)


def make_run_id(source_sha: Optional[str] = None) -> str:
    timestamp = utc_now_text().replace("-", "").replace(":", "").replace("Z", "Z").replace(".", ".")
    suffix = (source_sha or "nogit")[:7]
    host = re.sub(r"[^a-zA-Z0-9_.-]+", "-", platform.node()).strip("-") or "host"
    return f"{timestamp}_{suffix}_{host}"


def _lifecycle_event(stage: LifecycleStage, started: str, ended: Optional[str] = None, outcome: str = "completed") -> Dict[str, Any]:
    return {"stage": stage.value, "started_at_utc": started, "ended_at_utc": ended or utc_now_text(), "outcome": outcome}


def _load_events(path: Path) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    assertions: List[Dict[str, Any]] = []
    measurements: List[Dict[str, Any]] = []
    if not path.is_file():
        return assertions, measurements
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            assertions.append({"name": f"events_line_{line_number}", "pass": False, "detail": "malformed JSON event"})
            continue
        if event.get("type") == "assertion":
            assertions.append({"name": event.get("name"), "pass": bool(event.get("passed")), "detail": event.get("detail")})
        elif event.get("type") == "measurement":
            measurements.append(event)
    return assertions, measurements


def execute_single(
    plan: PlannedTest,
    executor: str,
    seed: int | None = None,
    results_root: Path | None = None,
    command_line: List[str] | None = None,
    source_context: Dict[str, Any] | None = None,
) -> tuple[TestStatus, Path]:
    repo = repository_root()
    results_root = results_root or tests_root() / "results"
    source = collect_source_identity(repo)
    source["qualification"] = source_context or {"kind": "local"}
    run_id = make_run_id(source.get("sha"))
    evidence = EvidenceRun(results_root, run_id)
    selected_seed = seed if seed is not None else random.SystemRandom().randrange(0, 2**31)
    run_started_utc = utc_now_text()
    run_started_mono = monotonic_seconds()
    manifest = plan.manifest
    profile_name = plan.profile.name if plan.profile else "unsupported"
    credit = plan.profile.evidence_credit if plan.profile else EvidenceCredit.NONE
    lifecycle: List[Dict[str, Any]] = []
    status = plan.status
    failure: Optional[Dict[str, Any]] = None
    test_started_utc = utc_now_text()
    test_started_mono = monotonic_seconds()
    test_path = evidence.test_path(manifest.test_id)
    attachments = test_path / "attachments"
    attachments.mkdir(parents=True, exist_ok=True)
    lifecycle.append(_lifecycle_event(LifecycleStage.DISCOVER, test_started_utc))
    lifecycle.append(_lifecycle_event(LifecycleStage.VALIDATE, utc_now_text()))
    lifecycle.append(_lifecycle_event(LifecycleStage.PREFLIGHT, utc_now_text(), outcome=plan.reason))
    lock_set: Optional[ResourceLockSet] = None
    try:
        if status in {TestStatus.BLOCKED, TestStatus.MANUAL_REQUIRED, TestStatus.SKIP}:
            failure = {"kind": status.value, "message": plan.reason}
        else:
            status = TestStatus.ERROR
            lock_set = ResourceLockSet(manifest.exclusive_resources)
            reserve_started = utc_now_text()
            lock_set.acquire()
            lifecycle.append(_lifecycle_event(LifecycleStage.RESERVE, reserve_started))
            context_path = test_path / "context.json"
            context = {
                "schema_version": 1,
                "run_id": run_id,
                "test_id": manifest.test_id,
                "profile": profile_name,
                "seed": selected_seed,
                "repository": str(repo),
                "test_output": str(test_path),
                "timeout_seconds": manifest.timeout_seconds,
                "run_pr1_vitest": (
                    profile_name in {"pr1-unit", "cross-language"}
                    and bool(manifest.raw.get("implementation", {}).get("pr1_vitest", False))
                ),
                "run_c_vectors": profile_name == "cross-language",
            }
            atomic_write_json(context_path, context)
            lifecycle.append(_lifecycle_event(LifecycleStage.PROVISION, utc_now_text()))
            lifecycle.append(_lifecycle_event(LifecycleStage.STIMULATE, utc_now_text()))
            outer_junit = attachments / "runner-pytest.xml"
            python_path = os.pathsep.join([str(repo), str(repo / "backend"), os.environ.get("PYTHONPATH", "")])
            command = [
                sys.executable, "-m", "pytest", "-q", str(manifest.entrypoint),
                "-p", "tests._framework.pytest_plugin", f"--junitxml={outer_junit}",
            ]
            command_result = run_command(
                command,
                cwd=repo,
                timeout_seconds=manifest.timeout_seconds,
                environment={"THERMOMETER_TEST_CONTEXT": str(context_path), "PYTHONPATH": python_path},
            )
            atomic_write_text(attachments / "runner.stdout.log", command_result.stdout)
            atomic_write_text(attachments / "runner.stderr.log", command_result.stderr)
            lifecycle.append(_lifecycle_event(LifecycleStage.OBSERVE, utc_now_text()))
            if command_result.timed_out:
                status = TestStatus.TIMEOUT
                failure = {"kind": "TIMEOUT", "message": f"test exceeded {manifest.timeout_seconds:.1f} seconds"}
            elif command_result.returncode == 0:
                status = TestStatus.PASS
            elif command_result.returncode == 1:
                status = TestStatus.FAIL
                failure = {"kind": "ASSERTION", "message": command_result.stderr.strip() or command_result.stdout[-2000:]}
            else:
                status = TestStatus.ERROR
                failure = {"kind": "PYTEST", "message": command_result.stderr.strip() or command_result.stdout[-2000:]}
            lifecycle.append(_lifecycle_event(LifecycleStage.EVALUATE, utc_now_text(), outcome=status.value))
    except ResourceBusyError as error:
        status = TestStatus.BLOCKED
        failure = {"kind": "RESOURCE_BUSY", "message": str(error)}
    except KeyboardInterrupt:
        status = TestStatus.ABORTED
        failure = {"kind": "ABORTED", "message": "operator interrupted the test"}
    except Exception as error:
        status = TestStatus.ERROR
        failure = {"kind": type(error).__name__, "message": str(error)}
    finally:
        teardown_started = utc_now_text()
        if lock_set is not None:
            try:
                lock_set.release()
                lifecycle.append(_lifecycle_event(LifecycleStage.TEARDOWN, teardown_started))
            except Exception as error:
                status = TestStatus.ERROR
                failure = {"kind": "TEARDOWN", "message": str(error)}
                lifecycle.append(_lifecycle_event(LifecycleStage.TEARDOWN, teardown_started, outcome="error"))
        else:
            lifecycle.append(_lifecycle_event(LifecycleStage.TEARDOWN, teardown_started, outcome="not reserved"))
    assertions, measurements = _load_events(test_path / "events.jsonl")
    effective_credit = credit if status is TestStatus.PASS else EvidenceCredit.NONE
    requirement_results = [
        {"jira": ref.jira, "uid": ref.uid, "status": status.value, "credit": effective_credit.value}
        for ref in manifest.requirements
    ]
    ended_utc = utc_now_text()
    lifecycle.append(_lifecycle_event(LifecycleStage.PUBLISH, ended_utc))
    selected_capabilities = [item.name for item in plan.capabilities]
    result = TestResult(
        schema_version=1,
        run_id=run_id,
        test_id=manifest.test_id,
        profile=profile_name,
        status=status,
        evidence_credit=effective_credit,
        started_at_utc=test_started_utc,
        ended_at_utc=ended_utc,
        duration_seconds=monotonic_seconds() - test_started_mono,
        executor={"display_name": executor, "identity": executor},
        requirements=requirement_results,
        lifecycle=lifecycle,
        measurements=measurements,
        assertions=assertions,
        environment={
            "capabilities": [item.__dict__ for item in plan.capabilities],
            "tool_versions": collect_tool_versions(selected_capabilities),
            **collect_environment(),
        },
        failure=failure,
    )
    run_record = {
        "schema_version": 1,
        "runner_version": RUNNER_VERSION,
        "run_id": run_id,
        "command_line": command_line or sys.argv,
        "selected_tests": [manifest.test_id],
        "requested_profile": profile_name,
        "seed": selected_seed,
        "started_at_utc": run_started_utc,
        "ended_at_utc": ended_utc,
        "duration_seconds": monotonic_seconds() - run_started_mono,
        "initiator": getpass.getuser(),
        "executor": executor,
        "execution_source": os.environ.get("THERMOMETER_EXECUTION_SOURCE", "local"),
        "source": source,
        "environment": collect_environment(),
        "requirements_baseline_sha256": json.loads((tests_root() / "requirements.lock.json").read_text(encoding="utf-8"))["baseline_sha256"],
        "jira_snapshot_date": "2026-09-11",
    }
    try:
        evidence.write_result(result)
        final_path = evidence.finalize(run_record)
    except Exception as error:
        final_path = evidence.preserve_incomplete(
            f"evidence publication failed: {type(error).__name__}: {error}"
        )
        return TestStatus.INCOMPLETE, final_path
    return status, final_path
