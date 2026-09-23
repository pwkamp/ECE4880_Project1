"""Human-readable qualification summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write(run: dict[str, Any], results: list[dict[str, Any]], coverage: dict[str, Any], path: Path) -> None:
    outcome_counts = {state: sum(item["outcome"] == state for item in results) for state in ("PASS", "FAIL", "BLOCKED", "SKIPPED", "NOT_APPLICABLE")}
    lines = [
        "# ECE4880 Verification Summary",
        "",
        f"- Run: `{run['run_id']}`",
        f"- Profile: `{run['profile']}`",
        f"- Git: `{run.get('git_sha') or 'unknown'}` ({run.get('git_state')})",
        f"- Test outcomes: " + ", ".join(f"{name}={value}" for name, value in outcome_counts.items()),
        f"- Requirement outcomes: " + ", ".join(f"{name}={value}" for name, value in coverage["counts"].items()),
        "",
        "## Tests",
        "",
        "| Test | Setup section | Method | Outcome | Human intervention / limitation |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        note = result.get("human_intervention") or "; ".join(result.get("limitations", [])) or "None"
        lines.append(f"| {result['test_id']} — {result['title']} | {result.get('setup_group', 'software')} | {result['method']} | {result['outcome']} | {note.replace('|', '/')} |")
    lines.extend(["", "## Requirements requiring human evidence", ""])
    human = [row for row in coverage["requirements"] if row["human_tests"]]
    for row in human:
        lines.append(f"- `{row['uid']}` ({row['jira']}): {', '.join(row['human_tests'])}; current result **{row['result']}**.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
