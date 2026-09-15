"""Command-line interface for catalog validation, planning, and one-test runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Sequence

from tests._framework.discovery import discover, tests_root
from tests._framework.execution import execute_single
from tests._framework.models import TestStatus
from tests._framework.planning import plan_tests, select_tests
from tests._framework.reporting import load_run, verify_run
from tests._framework.validation import validate_catalog


EXIT_BY_STATUS = {
    TestStatus.PASS: 0,
    TestStatus.FAIL: 1,
    TestStatus.ERROR: 2,
    TestStatus.BLOCKED: 3,
    TestStatus.SKIP: 3,
    TestStatus.MANUAL_REQUIRED: 3,
    TestStatus.TIMEOUT: 1,
    TestStatus.ABORTED: 130,
    TestStatus.INCOMPLETE: 4,
}


def _add_selection(parser: argparse.ArgumentParser, allow_all: bool = True) -> None:
    parser.add_argument("--test", action="append", default=[], help="consolidated test ID; repeatable")
    parser.add_argument("--group", choices=["gov", "doc", "sys", "hw", "fw", "ble", "con", "db", "web", "alr"])
    parser.add_argument("--requirement", help="Jira key, for example SCRUM-521")
    parser.add_argument("--uid", help="requirement UID, for example INT-LLR-414")
    parser.add_argument("--feasibility", help="case-insensitive feasibility substring")
    parser.add_argument(
        "--changed-component",
        help="select manifests owned by a changed component",
    )
    parser.add_argument(
        "--credit",
        choices=["FULL", "PARTIAL", "SUPPORTING_ONLY", "NONE"],
        help="select the requested profile's qualification-credit level",
    )
    if allow_all:
        parser.add_argument("--all", action="store_true", help="select all tests remaining after filters")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tests.runner", description="Thermometer requirement test runner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", help="list consolidated tests")
    list_parser.add_argument("--json", action="store_true")
    validate_parser = subparsers.add_parser("validate", help="validate schemas and complete traceability")
    validate_parser.add_argument("--json", action="store_true")
    plan_parser = subparsers.add_parser("plan", help="perform read-only capability planning")
    plan_parser.add_argument("--profile", required=True)
    plan_parser.add_argument("--json", action="store_true")
    _add_selection(plan_parser)
    run_parser = subparsers.add_parser("run", help="run one consolidated test")
    run_parser.add_argument("--profile", required=True)
    run_parser.add_argument("--test", action="append", required=True)
    run_parser.add_argument("--executor", required=True)
    run_parser.add_argument("--seed", type=int)
    run_parser.add_argument("--results-dir", type=Path)
    run_parser.add_argument(
        "--source-kind",
        choices=["local", "main", "pr", "integration"],
        default="local",
        help="identity of the source under qualification",
    )
    run_parser.add_argument("--pr-number", type=int)
    run_parser.add_argument("--pr-head-sha")
    run_parser.add_argument("--integration-sha")
    report_parser = subparsers.add_parser("report", help="verify and summarize an immutable run")
    report_parser.add_argument("--run", required=True)
    report_parser.add_argument("--json", action="store_true")
    return parser


def _selection(args: argparse.Namespace, manifests: Sequence[object]) -> List[object]:
    return select_tests(
        manifests,
        test_ids=getattr(args, "test", []),
        group=getattr(args, "group", None),
        requirement=getattr(args, "requirement", None),
        uid=getattr(args, "uid", None),
        feasibility=getattr(args, "feasibility", None),
        changed_component=getattr(args, "changed_component", None),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        report = validate_catalog()
        payload = {
            "valid": report.valid,
            "test_count": report.test_count,
            "requirement_count": report.requirement_count,
            "legacy_test_count": report.legacy_test_count,
            "errors": report.errors,
            "warnings": report.warnings,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Tests: {report.test_count}; requirements: {report.requirement_count}; existing Python tests: {report.legacy_test_count}")
            for message in report.errors:
                print(f"ERROR: {message}")
            for message in report.warnings:
                print(f"WARNING: {message}")
            print("VALID" if report.valid else "INVALID")
        return 0 if report.valid else 2
    manifests = discover()
    if args.command == "list":
        payload = [
            {"id": item.test_id, "name": item.name, "profiles": sorted(item.profiles), "feasibility": item.feasibility}
            for item in manifests
        ]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for item in payload:
                print(f"{item['id']:<8} {item['name']} [{', '.join(item['profiles'])}]")
        return 0
    if args.command == "plan":
        selected = _selection(args, manifests)
        if not selected:
            print("No tests matched the selection.", file=sys.stderr)
            return 2
        plans = plan_tests(selected, args.profile)
        if args.credit:
            plans = [
                item
                for item in plans
                if (
                    item.profile.evidence_credit.value
                    if item.profile is not None
                    else "NONE"
                )
                == args.credit
            ]
            if not plans:
                print("No tests matched the requested evidence credit.", file=sys.stderr)
                return 2
        payload = [
            {
                "id": item.manifest.test_id,
                "status": item.status.value,
                "reason": item.reason,
                "evidence_credit": item.profile.evidence_credit.value if item.profile else "NONE",
                "capabilities": [capability.__dict__ for capability in item.capabilities],
            }
            for item in plans
        ]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for item in payload:
                print(f"{item['id']:<8} {item['status']:<15} {item['reason']}")
        return 0
    if args.command == "run":
        validation = validate_catalog()
        if not validation.valid:
            for message in validation.errors:
                print(f"ERROR: {message}", file=sys.stderr)
            return 2
        selected = select_tests(manifests, test_ids=args.test)
        if len(selected) != 1 or len(args.test) != 1:
            print("Phase 1 runner executes exactly one --test per run; use plan for multi-test selection.", file=sys.stderr)
            return 2
        plan = plan_tests(selected, args.profile)[0]
        if args.profile in {"pr1-unit", "cross-language"}:
            if args.source_kind not in {"pr", "integration"}:
                print(
                    "PR #1 profiles require --source-kind pr or integration.",
                    file=sys.stderr,
                )
                return 2
            if args.pr_number != 1 or not args.pr_head_sha:
                print(
                    "PR #1 profiles require --pr-number 1 and --pr-head-sha.",
                    file=sys.stderr,
                )
                return 2
            if args.source_kind == "integration" and not args.integration_sha:
                print(
                    "An integration source requires --integration-sha.",
                    file=sys.stderr,
                )
                return 2
        status, path = execute_single(
            plan,
            executor=args.executor,
            seed=args.seed,
            results_root=args.results_dir,
            command_line=list(argv) if argv is not None else sys.argv,
            source_context={
                "kind": args.source_kind,
                "pr_number": args.pr_number,
                "pr_head_sha": args.pr_head_sha,
                "integration_sha": args.integration_sha,
            },
        )
        print(f"{selected[0].test_id}: {status.value}; evidence: {path}")
        return EXIT_BY_STATUS[status]
    if args.command == "report":
        run_path = tests_root() / "results" / args.run
        errors = verify_run(run_path)
        if not run_path.is_dir():
            print(f"run not found: {run_path}", file=sys.stderr)
            return 2
        record = load_run(run_path)
        if args.json:
            print(json.dumps({"run": record, "integrity_errors": errors}, indent=2))
        else:
            print((run_path / "summary.md").read_text(encoding="utf-8"))
            for message in errors:
                print(f"ERROR: {message}")
        return 4 if errors else 0
    return 2
