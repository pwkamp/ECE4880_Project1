#!/usr/bin/env python3
"""Requirements-driven qualification runner for the ECE4880 thermometer."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verification.core.catalog import PROFILES, CatalogError, load_catalog, validate_catalogs
from verification.core.environment import collect
from verification.core.evidence import write_json
from verification.core.execution import blocked_result, run_automated, run_manual
from verification.core.preflight import CONFIRMED, blockers, confirmations_pending, run_preflight
from verification.core.services import ServiceManager
from verification.reporters import coverage as coverage_reporter
from verification.reporters import dashboard_data, junit, markdown


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parent
ARTIFACTS = REPOSITORY / "artifacts" / "verification"
DASHBOARD = ROOT / "dashboard"


def _setup_group(test: dict[str, Any]) -> str:
    return str(test.get("setup_group", "software"))


def _ordered_by_setup(tests: list[dict[str, Any]], groups: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep compatible instrumentation together and preserve catalog order."""

    positions = {test["id"]: index for index, test in enumerate(tests)}
    return sorted(
        tests,
        key=lambda test: (int(groups[_setup_group(test)]["order"]), positions[test["id"]]),
    )


def _print_setup_plan(tests: list[dict[str, Any]], groups: dict[str, Any]) -> None:
    print("\nExecution sections")
    print("-" * 80)
    grouped: dict[str, list[str]] = {}
    for test in _ordered_by_setup(tests, groups):
        grouped.setdefault(_setup_group(test), []).append(test["id"])
    for group_id in sorted(grouped, key=lambda value: int(groups[value]["order"])):
        group = groups[group_id]
        pause = "operator setup confirmation required" if group.get("pause") else "runs unattended"
        print(f"  {group['order']:>2}. {group['title']} [{pause}]")
        print(f"      Tests: {', '.join(grouped[group_id])}")


def _available_uart_ports() -> list[str]:
    try:
        from serial.tools import list_ports

        return [port.device for port in list_ports.comports()]
    except ImportError:
        return []


def _prepare_setup_section(
    group_id: str,
    group: dict[str, Any],
    tests: list[dict[str, Any]],
    non_interactive: bool,
) -> tuple[bool, dict[str, Any]]:
    """Display and record the physical wiring boundary before a test section."""

    print("\n" + "=" * 80)
    print(f"SETUP SECTION: {group['title']}")
    print("=" * 80)
    print(f"Tests in this section: {', '.join(test['id'] for test in tests)}")
    for index, instruction in enumerate(group["instructions"], 1):
        print(f"  {index}. {instruction}")
    record: dict[str, Any] = {
        "setup_group": group_id,
        "title": group["title"],
        "tests": [test["id"] for test in tests],
        "instructions": list(group["instructions"]),
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "uart_port": os.environ.get("THERMOMETER_UART_PORT"),
    }
    if not group.get("pause"):
        print("No physical setup change is required; continuing automatically.")
        record.update(confirmed=True, response="automatic")
        return True, record
    if non_interactive or not sys.stdin.isatty():
        print("Operator setup confirmation is unavailable; this section will be BLOCKED.")
        record.update(confirmed=False, response="non-interactive")
        return False, record

    if group.get("uart_required") and not os.environ.get("THERMOMETER_UART_PORT"):
        ports = _available_uart_ports()
        print("\nDetected serial ports:")
        for index, port in enumerate(ports, 1):
            print(f"  {index}. {port}")
        prompt = "Select the ESP32 port number or type its name (for example COM8); leave blank to block this section: "
        raw = input(prompt).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(ports):
            raw = ports[int(raw) - 1]
        if not raw:
            record.update(confirmed=False, response="UART port not supplied")
            return False, record
        os.environ["THERMOMETER_UART_PORT"] = raw
        record["uart_port"] = raw
        print(f"UART capture will use {raw}. ESP-IDF Monitor must remain closed.")

    print("\nConfirm this complete setup before any test in the section starts:")
    print("  1. Ready - begin this section")
    print("  2. Cannot prepare - record every test in this section as BLOCKED")
    while True:
        response = input("Select: ").strip()
        if response in {"1", "2"}:
            break
        print("Enter 1 or 2.")
    confirmed = response == "1"
    record.update(confirmed=confirmed, response="ready" if confirmed else "cannot prepare")
    return confirmed, record


def _qualification_outcome(results: list[dict[str, Any]], coverage: dict[str, Any]) -> str:
    """Distinguish failed assertions from incomplete/blocked qualification."""

    if any(item["outcome"] == "FAIL" for item in results) or coverage["counts"]["UNMAPPED"]:
        return "FAIL"
    if any(item["outcome"] in {"BLOCKED", "SKIPPED"} for item in results):
        return "BLOCKED"
    return "PASS"


def _selected(tests: list[dict[str, Any]], profile: str) -> list[dict[str, Any]]:
    return [test for test in tests if profile in test.get("profiles", [])]


def _print_preflight(profile: str, tests: list[dict[str, Any]], fixtures: dict[str, Any], instrumentation: dict[str, Any]) -> None:
    print("ECE4880 Verification Preflight")
    print("=" * 30)
    print(f"Profile: {profile}")
    print("\nFixtures")
    for item in fixtures.values():
        print(f"  {item['name']:.<34} {item['status']} ({item['detail']})")
    print("\nInstrumentation")
    for item in instrumentation.values():
        print(f"  {item['name']:.<34} {item['status']}")
    blocked = sum(bool(blockers(test, fixtures, instrumentation)) for test in tests)
    pending = sum(
        not blockers(test, fixtures, instrumentation)
        and bool(confirmations_pending(test, fixtures, instrumentation))
        for test in tests
    )
    runnable = len(tests) - blocked - pending
    print(f"\nTests: {runnable} ready, {pending} awaiting operator confirmation, {blocked} blocked by preflight")


def preflight(profile: str) -> int:
    _, tests, fixture_catalog = validate_catalogs(ROOT)
    setup_groups = load_catalog(ROOT / "setup_groups.yaml")
    selected = _selected(tests, profile)
    fixture_status, instrumentation_status = run_preflight(selected, fixture_catalog, REPOSITORY)
    _print_setup_plan(selected, setup_groups)
    _print_preflight(profile, selected, fixture_status, instrumentation_status)
    return 1 if any(blockers(test, fixture_status, instrumentation_status) for test in selected) else 0


def run(profile: str, non_interactive: bool, defer_photos: bool = False, start_services: bool = True) -> int:
    requirements, tests, fixture_catalog = validate_catalogs(ROOT)
    setup_groups = load_catalog(ROOT / "setup_groups.yaml")
    selected = _selected(tests, profile)
    now = datetime.now(timezone.utc)
    started_monotonic = time.perf_counter_ns()
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPOSITORY, capture_output=True, text=True, check=False, timeout=5).stdout.strip() or "nogit"
    except (OSError, subprocess.TimeoutExpired):
        sha = "nogit"
    base_run_id = now.strftime("%Y-%m-%dT%H%M%SZ") + f"_{sha}"
    run_id = base_run_id
    suffix = 2
    while (ARTIFACTS / run_id).exists():
        run_id = f"{base_run_id}_{suffix}"
        suffix += 1
    run_dir = ARTIFACTS / run_id
    evidence_root = run_dir / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=False)

    service_events: list[dict[str, Any]] = []
    if profile in {"hil", "full"} and start_services:
        print("\nStarting or reusing backend, MySQL, and frontend fixtures (existing database retained)...")
        try:
            service_events = ServiceManager(REPOSITORY, evidence_root / "_services").ensure()
        except RuntimeError as exc:
            print(f"Fixture startup failed: {exc}", file=sys.stderr)

    fixture_status, instrumentation_status = run_preflight(selected, fixture_catalog, REPOSITORY)
    _print_setup_plan(selected, setup_groups)
    _print_preflight(profile, selected, fixture_status, instrumentation_status)

    metadata = collect(REPOSITORY, ROOT, profile, run_id)
    write_json(run_dir / "run.json", metadata)
    write_json(run_dir / "fixture-status.json", fixture_status)
    write_json(run_dir / "instrumentation-status.json", instrumentation_status)
    write_json(run_dir / "service-startup.json", service_events)
    catalog_dir = run_dir / "catalogs"
    catalog_dir.mkdir(exist_ok=True)
    for name in ("requirements.yaml", "tests.yaml", "fixtures.yaml", "setup_groups.yaml"):
        shutil.copy2(ROOT / name, catalog_dir / name)

    results: list[dict[str, Any]] = []
    setup_records: list[dict[str, Any]] = []
    ordered = _ordered_by_setup(selected, setup_groups)
    current_group_id: str | None = None
    current_group_ready = True
    for test in ordered:
        group_id = _setup_group(test)
        if group_id != current_group_id:
            section_tests = [item for item in ordered if _setup_group(item) == group_id]
            current_group_ready, setup_record = _prepare_setup_section(
                group_id, setup_groups[group_id], section_tests, non_interactive
            )
            setup_records.append(setup_record)
            write_json(run_dir / "setup-transitions.json", setup_records)
            current_group_id = group_id
        print(f"\n[{test['id']}] {test['title']}")
        reasons = blockers(test, fixture_status, instrumentation_status)
        if not current_group_ready:
            reasons.append(f"setup section {group_id} was not prepared and confirmed by the operator")
        if reasons:
            result = blocked_result(run_id, test, fixture_status, instrumentation_status, reasons)
        elif test["method"] == "automated":
            result = run_automated(REPOSITORY, evidence_root, run_id, test, fixture_status, instrumentation_status)
        else:
            result = run_manual(evidence_root, run_id, test, fixture_status, instrumentation_status, non_interactive, defer_photos, REPOSITORY)
            if result["outcome"] != "BLOCKED":
                for name in test.get("fixtures", []):
                    if fixture_status[name]["status"] == "CONFIRM_REQUIRED":
                        fixture_status[name]["status"] = CONFIRMED
                        fixture_status[name]["detail"] = f"confirmed during {test['id']}"
                for name in test.get("instrumentation", []):
                    if instrumentation_status[name]["status"] == "CONFIRM_REQUIRED":
                        instrumentation_status[name]["status"] = CONFIRMED
                        instrumentation_status[name]["detail"] = f"confirmed during {test['id']}"
        print(f"  -> {result['outcome']}")
        results.append(result)
        with (run_dir / "results.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, sort_keys=True) + "\n")

    coverage = coverage_reporter.calculate(requirements, tests, results)
    coverage_reporter.write(coverage, run_dir / "requirements-coverage.json", run_dir / "requirements-coverage.csv")
    junit.write(results, run_dir / "junit.xml")
    metadata["ended_at_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["duration_ms"] = (time.perf_counter_ns() - started_monotonic) // 1_000_000
    metadata["outcome"] = _qualification_outcome(results, coverage)
    write_json(run_dir / "run.json", metadata)
    write_json(run_dir / "fixture-status.json", fixture_status)
    write_json(run_dir / "instrumentation-status.json", instrumentation_status)
    markdown.write(metadata, results, coverage, run_dir / "summary.md")
    dashboard_data.publish(run_dir, DASHBOARD)
    print(f"\nArtifacts: {run_dir}")
    print(f"Qualification outcome: {metadata['outcome']}")
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[metadata["outcome"]]


def _latest_run() -> Path | None:
    marker = ARTIFACTS / "latest"
    if not marker.exists():
        return None
    path = ARTIFACTS / marker.read_text(encoding="utf-8").strip()
    return path if path.is_dir() else None


def status() -> int:
    latest = _latest_run()
    if latest is None:
        print("No verification run has been recorded.")
        return 1
    print((latest / "summary.md").read_text(encoding="utf-8"))
    return 0


def report(run_id: str) -> int:
    run_dir = _latest_run() if run_id == "latest" else ARTIFACTS / run_id
    if run_dir is None or not run_dir.is_dir():
        print(f"verification run not found: {run_id}", file=sys.stderr)
        return 1
    print((run_dir / "summary.md").read_text(encoding="utf-8"))
    return 0


def _rebuild_run_outputs(run_dir: Path, results: list[dict[str, Any]]) -> None:
    """Recalculate every derived artifact after an evidence/adjudication edit."""

    results_path = run_dir / "results.jsonl"
    results_path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in results), encoding="utf-8")
    frozen = run_dir / "catalogs"
    if (frozen / "requirements.yaml").is_file() and (frozen / "tests.yaml").is_file():
        requirements = load_catalog(frozen / "requirements.yaml")
        tests = load_catalog(frozen / "tests.yaml")
    else:
        requirements, tests, _ = validate_catalogs(ROOT)
    coverage = coverage_reporter.calculate(requirements, tests, results)
    coverage_reporter.write(coverage, run_dir / "requirements-coverage.json", run_dir / "requirements-coverage.csv")
    junit.write(results, run_dir / "junit.xml")
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    metadata["outcome"] = _qualification_outcome(results, coverage)
    write_json(run_dir / "run.json", metadata)
    markdown.write(metadata, results, coverage, run_dir / "summary.md")
    dashboard_data.publish(run_dir, DASHBOARD)


def adjudicate(run_id: str, test_id: str, outcome: str, reason: str, operator: str) -> tuple[bool, str]:
    """Record a traceable operator decision for a non-automated test result."""

    run_dir = _latest_run() if run_id == "latest" else ARTIFACTS / run_id
    if run_dir is None or not run_dir.is_dir():
        return False, f"verification run not found: {run_id}"
    outcome = outcome.upper()
    if outcome not in {"PASS", "FAIL", "BLOCKED"}:
        return False, "manual outcome must be PASS, FAIL, or BLOCKED"
    if not reason.strip() or not operator.strip():
        return False, "operator and rationale are required"
    frozen_tests = run_dir / "catalogs" / "tests.yaml"
    if frozen_tests.is_file():
        tests = load_catalog(frozen_tests)
    else:
        _, tests, _ = validate_catalogs(ROOT)
    definition = next((item for item in tests if item["id"] == test_id), None)
    if definition is None:
        return False, f"test not found: {test_id}"
    if definition["method"] == "automated":
        return False, "automated results cannot be manually adjudicated"
    results_path = run_dir / "results.jsonl"
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line]
    result = next((item for item in results if item["test_id"] == test_id), None)
    if result is None:
        return False, f"test result not found: {test_id}"
    result.setdefault("original_outcome", result["outcome"])
    result["outcome"] = outcome
    result["adjudication"] = {
        "operator": operator.strip(),
        "reason": reason.strip(),
        "outcome": outcome,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if outcome == "PASS":
        result.pop("failure_reason", None)
    else:
        result["failure_reason"] = reason.strip()
    _rebuild_run_outputs(run_dir, results)
    return True, f"{test_id} recorded as {outcome} for {run_dir.name}"


def add_evidence(run_id: str, test_id: str, photos: list[str], complete: bool) -> int:
    run_dir = _latest_run() if run_id == "latest" else ARTIFACTS / run_id
    if run_dir is None or not run_dir.is_dir():
        print(f"verification run not found: {run_id}", file=sys.stderr)
        return 1
    results_path = run_dir / "results.jsonl"
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line]
    matches = [item for item in results if item["test_id"] == test_id]
    if not matches:
        print(f"test result not found: {test_id}", file=sys.stderr)
        return 1
    target_dir = run_dir / "evidence" / test_id / "photos"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for raw in photos:
        source = Path(raw).expanduser().resolve()
        if not source.is_file():
            print(f"photo not found: {source}", file=sys.stderr)
            return 1
        destination = target_dir / source.name
        counter = 2
        while destination.exists():
            destination = target_dir / f"{source.stem}-{counter}{source.suffix}"
            counter += 1
        shutil.copy2(source, destination)
        copied.append(destination.relative_to(run_dir).as_posix())
    result = matches[0]
    result.setdefault("evidence", []).extend(copied)
    result["pending_evidence"] = []
    if complete and result.get("outcome") == "BLOCKED" and "photo evidence deferred" in result.get("failure_reason", ""):
        result["outcome"] = "PASS"
        result.pop("failure_reason", None)
    _rebuild_run_outputs(run_dir, results)
    print(f"Added {len(copied)} photo(s) to {test_id}; outcome is {result['outcome']}")
    return 0


def dashboard(no_browser: bool) -> int:
    class DashboardHandler(SimpleHTTPRequestHandler):
        """Serve only static dashboard assets and redacted run artifacts."""

        def translate_path(self, path: str) -> str:
            request_path = unquote(urlparse(path).path)
            if request_path.startswith("/artifacts/verification/"):
                relative = request_path.removeprefix("/artifacts/verification/")
                base = ARTIFACTS.resolve()
            else:
                relative = request_path.lstrip("/") or "index.html"
                base = DASHBOARD.resolve()
            candidate = (base / relative).resolve()
            try:
                candidate.relative_to(base)
            except ValueError:
                return str(base / "__not_found__")
            if any(part.startswith(".") or part.lower().endswith(".env") for part in candidate.parts):
                return str(base / "__not_found__")
            return str(candidate)

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            if urlparse(self.path).path != "/api/adjudicate":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 64_000:
                    raise ValueError("invalid request size")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                ok, message = adjudicate(
                    str(payload.get("run_id", "latest")),
                    str(payload.get("test_id", "")),
                    str(payload.get("outcome", "")),
                    str(payload.get("reason", "")),
                    str(payload.get("operator", "")),
                )
                body = json.dumps({"ok": ok, "message": message}).encode("utf-8")
                self.send_response(200 if ok else 400)
            except (ValueError, json.JSONDecodeError) as exc:
                body = json.dumps({"ok": False, "message": str(exc)}).encode("utf-8")
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 8765), DashboardHandler)
    url = "http://127.0.0.1:8765"
    print(f"Verification dashboard: {url} (Ctrl+C to stop)")
    if not no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def requirements_check_jira() -> int:
    print("The local catalog is a frozen Jira snapshot.")
    print("Read-only comparison requires the Atlassian connector and is performed by the repository audit workflow; ordinary test execution never requires Jira credentials.")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("run", "preflight"):
        command = commands.add_parser(name)
        command.add_argument("profile", choices=PROFILES)
        if name == "run":
            command.add_argument("--non-interactive", action="store_true", help="record manual tests BLOCKED without prompting")
            command.add_argument("--defer-photos", action="store_true", help="run functional steps now and attach required photos later")
            command.add_argument("--no-start-services", action="store_true", help="do not automatically start missing backend/MySQL/frontend fixtures")
    commands.add_parser("status")
    dash = commands.add_parser("dashboard")
    dash.add_argument("--no-browser", action="store_true")
    report_parser = commands.add_parser("report")
    report_parser.add_argument("run_id")
    requirements_parser = commands.add_parser("requirements")
    requirements_parser.add_argument("action", choices=("check-jira",))
    evidence_parser = commands.add_parser("evidence")
    evidence_commands = evidence_parser.add_subparsers(dest="evidence_action", required=True)
    evidence_add = evidence_commands.add_parser("add")
    evidence_add.add_argument("run_id")
    evidence_add.add_argument("test_id")
    evidence_add.add_argument("--photo", action="append", required=True)
    evidence_add.add_argument("--complete", action="store_true", help="complete a photo-only blocked result after attaching evidence")
    adjudicate_parser = commands.add_parser("adjudicate", help="record PASS/FAIL/BLOCKED for a manual or semi-automated result")
    adjudicate_parser.add_argument("run_id")
    adjudicate_parser.add_argument("test_id")
    adjudicate_parser.add_argument("outcome", choices=("PASS", "FAIL", "BLOCKED"))
    adjudicate_parser.add_argument("--reason", required=True)
    adjudicate_parser.add_argument("--operator", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "run":
            return run(args.profile, args.non_interactive, args.defer_photos, not args.no_start_services)
        if args.command == "preflight":
            return preflight(args.profile)
        if args.command == "status":
            return status()
        if args.command == "dashboard":
            return dashboard(args.no_browser)
        if args.command == "report":
            return report(args.run_id)
        if args.command == "requirements":
            return requirements_check_jira()
        if args.command == "evidence" and args.evidence_action == "add":
            return add_evidence(args.run_id, args.test_id, args.photo, args.complete)
        if args.command == "adjudicate":
            ok, message = adjudicate(args.run_id, args.test_id, args.outcome, args.reason, args.operator)
            print(message, file=sys.stdout if ok else sys.stderr)
            return 0 if ok else 1
    except CatalogError as exc:
        print(f"catalog error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
