"""Automated and guided-manual test execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence import write_json, write_text


EXIT_OUTCOMES = {0: "PASS", 2: "BLOCKED", 3: "SKIPPED", 4: "NOT_APPLICABLE"}
MANUAL_FIELDS = Path(__file__).resolve().parents[1] / "manual" / "fields.json"


def _choice(prompt: str, options: list[str]) -> str:
    print(prompt)
    for index, option in enumerate(options, 1):
        print(f"  {index}. {option}")
    while True:
        raw = input("Select: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        exact = [option for option in options if option.casefold() == raw.casefold()]
        if exact:
            return exact[0]
        print(f"Enter 1-{len(options)}.")


def _manual_measurements(test_id: str, defer_photos: bool = False) -> tuple[dict[str, Any], list[str]]:
    catalog = json.loads(MANUAL_FIELDS.read_text(encoding="utf-8"))
    values: dict[str, Any] = {}
    failures: list[str] = []
    for field in catalog.get(test_id, []):
        field_type = field.get("type", "text")
        if field_type == "boolean":
            raw = _choice(field["prompt"], ["Yes", "No"])
        elif field_type == "choice":
            raw = _choice(field["prompt"], list(field["choices"]))
        elif field_type == "photo" and defer_photos:
            raw = "DEFERRED"
            print(f"{field['prompt']}: deferred for later evidence attachment")
        else:
            raw = input(f"{field['prompt']}: ").strip()
        value: Any = raw
        try:
            if field_type == "number":
                value = float(raw)
            elif field_type == "integer":
                value = int(raw)
            elif field_type == "boolean":
                normalized = raw.casefold()
                if normalized not in {"yes", "y", "true", "no", "n", "false"}:
                    raise ValueError("enter yes or no")
                value = normalized in {"yes", "y", "true"}
            elif field_type == "choice":
                value = raw
            elif field_type == "photo":
                if raw != "DEFERRED" and not Path(raw).expanduser().exists():
                    raise ValueError("photo path does not exist (or run with --defer-photos)")
            elif not raw:
                raise ValueError("a value is required")
        except ValueError as exc:
            failures.append(f"{field['id']}: invalid value ({exc})")
            values[field["id"]] = raw
            continue
        values[field["id"]] = value
        if "expected" in field and value != field["expected"]:
            failures.append(f"{field['id']}: expected {field['expected']!r}, got {value!r}")
        if "minimum" in field and value < field["minimum"]:
            failures.append(f"{field['id']}: {value} is below {field['minimum']}")
        if "maximum" in field and value > field["maximum"]:
            failures.append(f"{field['id']}: {value} exceeds {field['maximum']}")
        if "exclusive_maximum" in field and value >= field["exclusive_maximum"]:
            failures.append(f"{field['id']}: {value} must be below {field['exclusive_maximum']}")
    return values, failures


def _base_result(run_id: str, test: dict[str, Any], fixtures: dict[str, Any], instrumentation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "test_id": test["id"],
        "title": test["title"],
        "subsystem": test["subsystem"],
        "method": test["method"],
        "setup_group": test.get("setup_group", "software"),
        "requirements": test.get("requirements", []),
        "jira_keys": test.get("jira_keys", []),
        "fixtures": {name: fixtures[name]["status"] for name in test.get("fixtures", [])},
        "instrumentation": {name: instrumentation[name]["status"] for name in test.get("instrumentation", [])},
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": test.get("limitations", []),
        "human_intervention": test.get("human_intervention"),
        "metrics": {},
        "evidence": [],
    }


def blocked_result(run_id: str, test: dict[str, Any], fixtures: dict[str, Any], instrumentation: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    result = _base_result(run_id, test, fixtures, instrumentation)
    result.update(outcome="BLOCKED", duration_ms=0, failure_reason="; ".join(reasons))
    return result


def run_automated(repository: Path, evidence_root: Path, run_id: str, test: dict[str, Any], fixtures: dict[str, Any], instrumentation: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(run_id, test, fixtures, instrumentation)
    test_evidence = evidence_root / test["id"]
    test_evidence.mkdir(parents=True, exist_ok=True)
    command = [str(part).replace("{python}", sys.executable) for part in test["entrypoint"]["command"]]
    started = time.perf_counter_ns()
    try:
        environment = os.environ.copy()
        environment["VERIFICATION_EVIDENCE_DIR"] = str(test_evidence.resolve())
        process = subprocess.run(command, cwd=repository, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=float(test.get("timeout_seconds", 600)), check=False)
        elapsed = (time.perf_counter_ns() - started) // 1_000_000
        log_path = test_evidence / "command.log"
        write_text(log_path, f"COMMAND: {command!r}\nEXIT: {process.returncode}\n\nSTDOUT\n{process.stdout}\nSTDERR\n{process.stderr}")
        result["evidence"].append(log_path.relative_to(evidence_root.parent).as_posix())
        for artifact in sorted(test_evidence.rglob("*")):
            if artifact.is_file() and artifact != log_path and not any(part.startswith(".") for part in artifact.relative_to(test_evidence).parts):
                result["evidence"].append(artifact.relative_to(evidence_root.parent).as_posix())
        result["duration_ms"] = elapsed
        result["outcome"] = EXIT_OUTCOMES.get(process.returncode, "FAIL")
        if process.returncode not in EXIT_OUTCOMES:
            result["failure_reason"] = f"command exited with {process.returncode}"
        metrics_file = test_evidence / "metrics.json"
        if metrics_file.exists():
            result["metrics"] = json.loads(metrics_file.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired as exc:
        result.update(outcome="FAIL", duration_ms=(time.perf_counter_ns() - started) // 1_000_000, failure_reason=f"timeout after {exc.timeout}s")
    except OSError as exc:
        result.update(outcome="BLOCKED", duration_ms=(time.perf_counter_ns() - started) // 1_000_000, failure_reason=str(exc))
    return result


def run_manual(evidence_root: Path, run_id: str, test: dict[str, Any], fixtures: dict[str, Any], instrumentation: dict[str, Any], non_interactive: bool, defer_photos: bool = False, repository: Path | None = None) -> dict[str, Any]:
    result = _base_result(run_id, test, fixtures, instrumentation)
    if non_interactive or not sys.stdin.isatty():
        result.update(outcome="BLOCKED", duration_ms=0, failure_reason="operator interaction required; rerun without --non-interactive in a terminal")
        return result
    if test.get("assisted_workflow"):
        from .assisted import run_assisted

        return run_assisted(repository or evidence_root.parents[3], evidence_root, result, test, defer_photos)
    started = time.perf_counter_ns()
    print(f"\n{test['id']} - {test['title']}\n{'=' * (len(test['id']) + len(test['title']) + 3)}")
    print(test.get("description", ""))
    if test.get("limitations"):
        print("This test does not cover: " + "; ".join(test["limitations"]))
    answers: dict[str, Any] = {}
    for item in test.get("manual_steps", []):
        print(f"\nSTEP: {item['instruction']}")
        value = _choice(item.get("prompt", "Result"), ["Yes / complete", "No / failed", "Cannot perform"])
        answers[item["id"]] = value
    print("\nSTRUCTURED MEASUREMENTS")
    measurements, measurement_failures = _manual_measurements(test["id"], defer_photos)
    outcome = _choice("Overall outcome", ["PASS", "FAIL", "BLOCKED"])
    normalized = {key: value.strip().casefold() for key, value in answers.items()}
    negative = {"n", "no", "false", "not ready", "failed", "fail", "no / failed", "cannot perform"}
    if normalized.get("setup") in negative:
        outcome = "BLOCKED"
    elif normalized.get("procedure") in negative or normalized.get("evidence") in negative:
        outcome = "FAIL"
    if measurement_failures:
        outcome = "FAIL"
    deferred = [key for key, value in measurements.items() if value == "DEFERRED"]
    functional_outcome = outcome
    if deferred and outcome == "PASS":
        outcome = "BLOCKED"
    operator = input("Operator initials: ").strip()
    comments = input("Comments (optional): ").strip()
    record = {
        "answers": answers,
        "measurements": measurements,
        "validation_failures": measurement_failures,
        "operator_initials": operator,
        "comments": comments,
        "deferred_evidence": deferred,
        "functional_outcome": functional_outcome,
    }
    path = evidence_root / test["id"] / "manual-evidence.json"
    write_json(path, record)
    result.update(outcome=outcome, duration_ms=(time.perf_counter_ns() - started) // 1_000_000)
    result["metrics"] = measurements
    if measurement_failures:
        result["failure_reason"] = "; ".join(measurement_failures)
    elif deferred:
        result["failure_reason"] = "required photo evidence deferred; attach it with the evidence add command"
        result["pending_evidence"] = deferred
    if outcome != "BLOCKED":
        for name, status in list(result["fixtures"].items()):
            if status == "CONFIRM_REQUIRED":
                result["fixtures"][name] = "CONFIRMED"
        for name, status in list(result["instrumentation"].items()):
            if status == "CONFIRM_REQUIRED":
                result["instrumentation"][name] = "CONFIRMED"
    result["evidence"].append(path.relative_to(evidence_root.parent).as_posix())
    return result
