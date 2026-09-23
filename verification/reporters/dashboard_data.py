"""Publish the latest run to the static dashboard."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from verification.core.evidence import safe_output_path
from verification.core.paths import within


REPOSITORY = Path(__file__).resolve().parents[2]
ARTIFACTS = REPOSITORY / "artifacts" / "verification"
DASHBOARD = REPOSITORY / "verification" / "dashboard"


def publish(run_dir: Path, dashboard_dir: Path) -> None:
    run_dir = within(run_dir, ARTIFACTS)
    dashboard_dir = within(dashboard_dir, DASHBOARD)
    history: dict[str, list[dict[str, object]]] = {}
    for candidate in sorted(run_dir.parent.iterdir(), reverse=True):
        results_path = candidate / "results.jsonl"
        run_path = candidate / "run.json"
        if not candidate.is_dir() or not results_path.is_file() or not run_path.is_file():
            continue
        historical_run = json.loads(run_path.read_text(encoding="utf-8"))
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            result = json.loads(line)
            history.setdefault(result["test_id"], []).append(
                {
                    "run_id": historical_run["run_id"],
                    "profile": historical_run["profile"],
                    "started_at_utc": result["started_at_utc"],
                    "outcome": result["outcome"],
                    "duration_ms": result["duration_ms"],
                    "evidence": result.get("evidence", []),
                }
            )
    repository = run_dir.parents[2]
    frozen_tests = run_dir / "catalogs" / "tests.yaml"
    test_catalog = frozen_tests if frozen_tests.is_file() else repository / "verification" / "tests.yaml"
    frozen_setup = run_dir / "catalogs" / "setup_groups.yaml"
    setup_catalog = frozen_setup if frozen_setup.is_file() else repository / "verification" / "setup_groups.yaml"
    transitions_path = run_dir / "setup-transitions.json"
    payload = {
        "run": json.loads((run_dir / "run.json").read_text(encoding="utf-8")),
        "results": [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if line],
        "coverage": json.loads((run_dir / "requirements-coverage.json").read_text(encoding="utf-8")),
        "fixtures": json.loads((run_dir / "fixture-status.json").read_text(encoding="utf-8")),
        "instrumentation": json.loads((run_dir / "instrumentation-status.json").read_text(encoding="utf-8")),
        "test_catalog": json.loads(test_catalog.read_text(encoding="utf-8")),
        "setup_groups": json.loads(setup_catalog.read_text(encoding="utf-8")),
        "setup_transitions": json.loads(transitions_path.read_text(encoding="utf-8")) if transitions_path.is_file() else [],
        "history": history,
    }
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    safe_output_path(dashboard_dir / "latest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    latest = safe_output_path(run_dir.parent / "latest")
    latest.write_text(run_dir.name + "\n", encoding="utf-8")
