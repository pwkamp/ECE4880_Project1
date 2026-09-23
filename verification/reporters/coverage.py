"""Requirement-to-test result reduction."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from verification.core.evidence import safe_output_path


def calculate(requirements: list[dict[str, Any]], tests: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    tests_by_requirement: dict[str, list[dict[str, Any]]] = {item["uid"]: [] for item in requirements}
    for test in tests:
        for uid in test.get("requirements", []):
            tests_by_requirement.setdefault(uid, []).append(test)
    results_by_id = {result["test_id"]: result for result in results}
    rows = []
    for requirement in requirements:
        mapped = tests_by_requirement.get(requirement["uid"], [])
        states = [results_by_id[item["id"]]["outcome"] for item in mapped if item["id"] in results_by_id]
        unresolved = requirement.get("status", "active").lower() in {"tbd", "conflict"}
        if unresolved:
            outcome = "BLOCKED"
            reason = f"Jira requirement status is {requirement['status']}"
        elif not mapped:
            outcome, reason = "FAIL", "unmapped requirement"
        elif any(state == "FAIL" for state in states):
            outcome, reason = "FAIL", "one or more executed mandatory tests failed"
        elif len(states) < len(mapped) or any(state in {"BLOCKED", "SKIPPED"} for state in states):
            outcome, reason = "BLOCKED", "mandatory verification is unexecuted, skipped, or blocked"
        elif states and all(state in {"PASS", "NOT_APPLICABLE"} for state in states):
            outcome, reason = "PASS", "all mandatory mapped tests passed"
        else:
            outcome, reason = "BLOCKED", "no conclusive evidence"
        rows.append({
            "uid": requirement["uid"],
            "jira": requirement["jira"],
            "level": requirement["level"],
            "component": requirement.get("component", ""),
            "requirement_status": requirement.get("status", "active"),
            "tests": [item["id"] for item in mapped],
            "automated_tests": [item["id"] for item in mapped if item["method"] == "automated"],
            "human_tests": [item["id"] for item in mapped if item["method"] != "automated"],
            "result": outcome,
            "reason": reason,
        })
    counts = {state: sum(1 for row in rows if row["result"] == state) for state in ("PASS", "FAIL", "BLOCKED", "SKIPPED", "NOT_APPLICABLE")}
    counts["UNMAPPED"] = sum(1 for row in rows if not row["tests"])
    return {"requirements": rows, "counts": counts, "total": len(rows)}


def write(report: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    json_path = safe_output_path(json_path)
    csv_path = safe_output_path(csv_path)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["uid", "jira", "level", "component", "requirement_status", "tests", "automated_tests", "human_tests", "result", "reason"])
        writer.writeheader()
        for row in report["requirements"]:
            writer.writerow({**row, "tests": ",".join(row["tests"]), "automated_tests": ",".join(row["automated_tests"]), "human_tests": ",".join(row["human_tests"])})
