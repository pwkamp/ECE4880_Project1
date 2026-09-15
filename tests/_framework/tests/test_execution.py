from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._framework.execution import _load_events, execute_single
from tests._framework.models import (
    CapabilityResult,
    EvidenceCredit,
    PlannedTest,
    Profile,
    RequirementRef,
    TestManifest as ManifestRecord,
    TestStatus as Status,
)
from tests._framework.process_supervisor import CommandResult
from tests._framework.reporting import verify_run


def make_plan(initial_status: Status = Status.PASS) -> PlannedTest:
    folder = Path(__file__).resolve().parents[2] / "ble_005_protocol_conformance"
    profile = Profile("unit", "automated", EvidenceCredit.FULL, ["python"])
    manifest = ManifestRecord(
        schema_version=1,
        test_id="BLE-005",
        name="Protocol",
        folder=folder,
        entrypoint=folder / "test_ble_005.py",
        owners=["integration"],
        requirements=[RequirementRef("SCRUM-506", "INT-MLR-407")],
        profiles={"unit": profile},
        timeout_seconds=10,
        exclusive_resources=[],
        feasibility="Runnable",
        implementation_status="implemented",
        raw={"implementation": {}},
    )
    reason = "ready to run" if initial_status is Status.PASS else "missing bench"
    return PlannedTest(
        manifest,
        profile,
        initial_status,
        reason,
        [CapabilityResult("python", True, "available")],
    )


def command_result(code: int | None = 0, timed_out: bool = False) -> CommandResult:
    return CommandResult(
        command=("python",),
        returncode=code,
        duration_seconds=0.01,
        timed_out=timed_out,
        stdout="output",
        stderr="error" if code else "",
    )


class ExecutionTests(unittest.TestCase):
    def execute_with(self, side_effect):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        patch_arguments = (
            {"side_effect": side_effect}
            if isinstance(side_effect, BaseException)
            else {"return_value": side_effect}
        )
        with patch("tests._framework.execution.run_command", **patch_arguments):
            status, path = execute_single(
                make_plan(),
                executor="Unit Tester",
                seed=1187,
                results_root=Path(temporary.name),
                command_line=["tests.runner", "run"],
            )
        result = json.loads(
            (path / "tests" / "BLE-005" / "result.json").read_text(encoding="utf-8")
        )
        return status, path, result

    def test_passing_test_is_published_with_full_credit(self) -> None:
        status, path, result = self.execute_with(command_result(0))
        self.assertEqual(status, Status.PASS)
        self.assertEqual(result["evidence_credit"], "FULL")
        self.assertEqual(verify_run(path), [])

    def test_assertion_exit_is_fail_and_removes_evidence_credit(self) -> None:
        status, _, result = self.execute_with(command_result(1))
        self.assertEqual(status, Status.FAIL)
        self.assertEqual(result["evidence_credit"], "NONE")

    def test_pytest_configuration_exit_is_error(self) -> None:
        status, _, result = self.execute_with(command_result(2))
        self.assertEqual(status, Status.ERROR)
        self.assertEqual(result["failure"]["kind"], "PYTEST")

    def test_timeout_is_distinct_from_failure(self) -> None:
        status, _, result = self.execute_with(command_result(None, timed_out=True))
        self.assertEqual(status, Status.TIMEOUT)
        self.assertEqual(result["failure"]["kind"], "TIMEOUT")

    def test_operator_abort_retains_an_aborted_result(self) -> None:
        status, _, result = self.execute_with(KeyboardInterrupt())
        self.assertEqual(status, Status.ABORTED)
        self.assertEqual(result["failure"]["kind"], "ABORTED")

    def test_blocked_preflight_does_not_start_native_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch("tests._framework.execution.run_command") as command:
                status, path = execute_single(
                    make_plan(Status.BLOCKED),
                    executor="Unit Tester",
                    results_root=Path(temporary),
                )
            command.assert_not_called()
            self.assertEqual(status, Status.BLOCKED)
            result = json.loads(
                (path / "tests" / "BLE-005" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(result["failure"]["kind"], "BLOCKED")

    def test_malformed_event_is_a_failed_recorded_assertion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            path.write_text("{bad json}\n", encoding="utf-8")
            assertions, measurements = _load_events(path)
        self.assertFalse(assertions[0]["pass"])
        self.assertEqual(measurements, [])


if __name__ == "__main__":
    unittest.main()
