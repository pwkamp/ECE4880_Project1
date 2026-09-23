"""Human-readable qualification summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.core.evidence import safe_output_path
from verification.core.outcomes import TEST_OUTCOMES, display_outcome


def write(run: dict[str, Any], results: list[dict[str, Any]], coverage: dict[str, Any], path: Path) -> None:
    path = safe_output_path(path)
    outcome_counts = {state: sum(item["outcome"] == state for item in results) for state in TEST_OUTCOMES}
    lines = [
        "# ECE4880 Verification Summary",
        "",
        f"- Run: `{run['run_id']}`",
        f"- Profile: `{run['profile']}`",
        f"- Git: `{run.get('git_sha') or 'unknown'}` ({run.get('git_state')})",
        f"- Test outcomes: " + ", ".join(f"{display_outcome(name)}={value}" for name, value in outcome_counts.items()),
        f"- Requirement outcomes: " + ", ".join(f"{name}={value}" for name, value in coverage["counts"].items()),
    ]
    if run.get("resumed_from_run"):
        lines.extend([
            f"- Resumed from: `{run['resumed_from_run']}`",
            f"- Imported unchanged results: {len(run.get('reused_test_ids', []))}",
            f"- Executed in this run: {len(run.get('executed_test_ids', []))}",
        ])
    lines.extend([
        "",
        "## Tests",
        "",
        "| Test | Setup section | Method | Outcome | Human intervention / limitation |",
        "|---|---|---|---|---|",
    ])
    for result in results:
        note = result.get("human_intervention") or "; ".join(result.get("limitations", [])) or "None"
        provenance = f"Imported from {result['reused_from_run']}" if result.get("reused") else "Executed in this run"
        note = f"{provenance}; {note}"
        lines.append(f"| {result['test_id']} — {result['title']} | {result.get('setup_group', 'software')} | {result['method']} | {display_outcome(result['outcome'])} | {note.replace('|', '/')} |")
    lines.extend(["", "## Requirements requiring human evidence", ""])
    human = [row for row in coverage["requirements"] if row["human_tests"]]
    for row in human:
        lines.append(f"- `{row['uid']}` ({row['jira']}): {', '.join(row['human_tests'])}; current result **{display_outcome(row['result'])}**.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
