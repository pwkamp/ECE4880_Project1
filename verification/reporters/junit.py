"""Minimal JUnit XML output for CI and IDE consumption."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from verification.core.outcomes import PASSING_OUTCOMES


def write(results: list[dict[str, Any]], path: Path) -> None:
    suite = ET.Element("testsuite", {
        "name": "ECE4880 qualification",
        "tests": str(len(results)),
        "failures": str(sum(item["outcome"] == "FAIL" for item in results)),
        "skipped": str(sum(item["outcome"] in {"BLOCKED", "SKIPPED", "NOT_APPLICABLE"} for item in results)),
        "time": f"{sum(item.get('duration_ms', 0) for item in results) / 1000:.3f}",
    })
    for result in results:
        case = ET.SubElement(suite, "testcase", {
            "classname": result["subsystem"],
            "name": f"{result['test_id']} {result['title']}",
            "time": f"{result.get('duration_ms', 0) / 1000:.3f}",
        })
        if result["outcome"] == "FAIL":
            ET.SubElement(case, "failure", {"message": result.get("failure_reason", "qualification failed")}).text = result.get("failure_reason", "")
        elif result["outcome"] not in PASSING_OUTCOMES:
            ET.SubElement(case, "skipped", {"message": result.get("failure_reason", result["outcome"])})
        ET.SubElement(case, "system-out").text = "\n".join(result.get("evidence", []))
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)
