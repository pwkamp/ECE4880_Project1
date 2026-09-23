from __future__ import annotations

import json
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

from verification.core.catalog import validate_catalogs
from verification.core.evidence import redact, safe_output_path
from verification.core.paths import existing_run
from verification.core.instrumentation import TimestampedLog, measure, write_database_capture
from verification.core.execution import _manual_measurements
from verification.core.services import ServiceManager
from verification.reporters.coverage import calculate
from verification.reporters.dashboard_data import publish
from verification.fixtures.fake_ble_device import FakeBleDevice
from verification.fixtures.fake_notification_provider import CaptureEmailProvider, FailingNotificationProvider
from verification.runner import _ordered_by_setup, _prepare_setup_section, _qualification_outcome


ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def test_run_outcome_distinguishes_blocked_from_failed(self) -> None:
        coverage = {"counts": {"UNMAPPED": 0}}
        self.assertEqual(_qualification_outcome([{"outcome": "PASS"}], coverage), "PASS")
        self.assertEqual(_qualification_outcome([{"outcome": "PASS"}, {"outcome": "BLOCKED"}], coverage), "BLOCKED")
        self.assertEqual(_qualification_outcome([{"outcome": "BLOCKED"}, {"outcome": "FAIL"}], coverage), "FAIL")

    def test_jira_snapshot_and_consolidated_matrix_are_complete(self) -> None:
        requirements, tests, _ = validate_catalogs(ROOT)
        self.assertEqual(len(requirements), 255)
        self.assertEqual(len(tests), 36)
        self.assertEqual(len({item["jira"] for item in requirements}), 255)
        for test in tests:
            with self.subTest(test=test["id"]):
                self.assertGreaterEqual(len(test["rationale"]), 100)

    def test_every_manual_entrypoint_has_a_procedure(self) -> None:
        _, tests, _ = validate_catalogs(ROOT)
        repository = ROOT.parent
        fields = json.loads((ROOT / "manual" / "fields.json").read_text(encoding="utf-8"))
        for test in tests:
            if test["method"] != "automated":
                with self.subTest(test=test["id"]):
                    self.assertTrue((repository / test["entrypoint"]["procedure"]).is_file())
                    self.assertIn(test["id"], fields)
                    self.assertTrue(fields[test["id"]])

    def test_tbd_and_conflict_requirements_remain_explicit(self) -> None:
        requirements, _, _ = validate_catalogs(ROOT)
        unresolved = {item["status"] for item in requirements if item["status"] != "active"}
        self.assertEqual(unresolved, {"tbd", "conflict"})

    def test_system_hlrs_are_not_claimed_by_simulation_alone(self) -> None:
        requirements, tests, _ = validate_catalogs(ROOT)
        methods = {
            requirement["uid"]: [
                test["method"]
                for test in tests
                if requirement["uid"] in test.get("requirements", [])
            ]
            for requirement in requirements
        }
        for requirement in requirements:
            if requirement["level"] == "HLR" and requirement["status"] == "active":
                with self.subTest(requirement=requirement["uid"]):
                    self.assertTrue(any(method != "automated" for method in methods[requirement["uid"]]))

    def test_unresolved_and_unexecuted_requirements_cannot_pass(self) -> None:
        requirements = [
            {"uid": "ACTIVE", "jira": "SCRUM-1", "level": "LLR", "component": "test", "status": "active"},
            {"uid": "TBD", "jira": "SCRUM-2", "level": "LLR", "component": "test", "status": "tbd"},
        ]
        tests = [{"id": "T-1", "method": "automated", "requirements": ["ACTIVE", "TBD"]}]
        report = calculate(requirements, tests, [])
        self.assertEqual([row["result"] for row in report["requirements"]], ["BLOCKED", "BLOCKED"])

    def test_tests_are_grouped_by_compatible_hardware_setup(self) -> None:
        _, tests, _ = validate_catalogs(ROOT)
        groups = json.loads((ROOT / "setup_groups.yaml").read_text(encoding="utf-8"))
        ordered = _ordered_by_setup(tests, groups)
        orders = [groups[test.get("setup_group", "software")]["order"] for test in ordered]
        self.assertEqual(orders, sorted(orders))
        power_cycle = [test for test in tests if test.get("setup_group") == "power_cycle_no_uart"]
        self.assertTrue(power_cycle)
        for test in power_cycle:
            instruments = " ".join(test["instrumentation"]).casefold()
            self.assertNotIn("uart", instruments)
            self.assertNotIn("serial", instruments)

    def test_noninteractive_hardware_setup_blocks_without_prompting(self) -> None:
        group = {"title": "Power test", "pause": True, "uart_required": False, "instructions": ["Disconnect USB"]}
        ready, record = _prepare_setup_section("power", group, [{"id": "TEST-1"}], True)
        self.assertFalse(ready)
        self.assertFalse(record["confirmed"])


class EvidenceTests(unittest.TestCase):
    def test_service_manager_writes_reused_service_evidence_on_fresh_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "artifacts" / "run-1" / "evidence" / "_services"
            manager = ServiceManager(root, evidence)
            with patch("verification.core.services.shutil.which", return_value="launcher"), patch(
                "verification.core.services._healthy", return_value=True
            ):
                events = manager.ensure()

            self.assertTrue((evidence / "service-startup.json").is_file())
            self.assertEqual([event["action"] for event in events], ["reused", "reused"])

    def test_dashboard_uses_the_catalog_frozen_with_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repository"
            run = repository / "artifacts" / "verification" / "run-1"
            dashboard = repository / "verification" / "dashboard-output"
            (run / "catalogs").mkdir(parents=True)
            (run / "catalogs" / "tests.yaml").write_text(
                json.dumps([{"id": "FROZEN", "rationale": "frozen"}]), encoding="utf-8"
            )
            (run / "catalogs" / "setup_groups.yaml").write_text(
                json.dumps({"software": {"title": "Frozen setup", "instructions": ["None"]}}), encoding="utf-8"
            )
            (run / "run.json").write_text(
                json.dumps({"run_id": "run-1", "profile": "full"}), encoding="utf-8"
            )
            result = {
                "test_id": "FROZEN", "profile": "full", "started_at_utc": "now",
                "outcome": "BLOCKED", "duration_ms": 0, "evidence": [],
            }
            (run / "results.jsonl").write_text(json.dumps(result) + "\n", encoding="utf-8")
            (run / "requirements-coverage.json").write_text(
                json.dumps({"counts": {}, "requirements": []}), encoding="utf-8"
            )
            (run / "fixture-status.json").write_text("{}", encoding="utf-8")
            (run / "instrumentation-status.json").write_text("{}", encoding="utf-8")

            with patch("verification.reporters.dashboard_data.ARTIFACTS", repository / "artifacts" / "verification"), patch(
                "verification.reporters.dashboard_data.DASHBOARD", dashboard
            ):
                publish(run, dashboard)

            payload = json.loads((dashboard / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["test_catalog"][0]["id"], "FROZEN")

    def test_run_lookup_rejects_traversal_and_escaped_latest_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory) / "artifacts"
            run = artifacts / "2026-09-23T035434Z_f096661"
            run.mkdir(parents=True)
            self.assertEqual(existing_run(artifacts, run.name), run.resolve())
            self.assertIsNone(existing_run(artifacts, "../../outside"))
            (artifacts / "latest").write_text("../../outside\n", encoding="utf-8")
            self.assertIsNone(existing_run(artifacts, "latest"))

    def test_verification_writer_rejects_paths_outside_approved_roots(self) -> None:
        outside = Path.home() / "verification-path-escape.txt"
        with self.assertRaises(ValueError):
            safe_output_path(outside)

    def test_common_secrets_are_redacted(self) -> None:
        value = redact("Authorization: Bearer abc\npassword=hunter2 mysql://u:p@mysql/db passkey=123456 MYSQL_ROOT_PASSWORD=rootpw mysql -pclipw")
        self.assertNotIn("abc", value)
        self.assertNotIn("hunter2", value)
        self.assertNotIn(":p@", value)
        self.assertNotIn("123456", value)
        self.assertNotIn("rootpw", value)
        self.assertNotIn("clipw", value)

    def test_shared_instrumentation_uses_monotonic_time_and_redacts_files(self) -> None:
        timed = measure(lambda: "value")
        self.assertEqual(timed.value, "value")
        self.assertGreaterEqual(timed.duration_ms, 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = TimestampedLog(root / "backend.log")
            log.append("Authorization: Bearer private")
            self.assertNotIn("private", (root / "backend.log").read_text())
            write_database_capture(
                root,
                query="SELECT 1",
                columns=["value"],
                before=[[1]],
                after=[[2]],
                explain={"plan": "constant"},
            )
            self.assertTrue((root / "database_before.csv").is_file())
            self.assertTrue((root / "database_after.csv").is_file())
            self.assertTrue((root / "explain.json").is_file())

    def test_structured_manual_limit_cannot_be_overridden(self) -> None:
        with patch("builtins.input", side_effect=["10", "10", "1000", "timings.csv"]):
            values, failures = _manual_measurements("SYS-04")
        self.assertEqual(values["maximum_end_to_end_latency_ms"], 1000.0)
        self.assertTrue(any("must be below 1000" in item for item in failures))


class FakeFixtureTests(unittest.TestCase):
    def test_fake_ble_supports_current_display_history_and_link_control(self) -> None:
        device = FakeBleDevice(history=[{"sample_seq": n, "temperature_c": 20 + n / 10} for n in range(10)])
        self.assertTrue(device.get_current()["average_valid"])
        self.assertTrue(device.set_display(1, True)["enabled"])
        self.assertEqual(device.get_history_meta()["count"], 10)
        self.assertEqual(len(device.get_history_chunk(0, 100)), 10)
        device.disconnect()
        with self.assertRaises(ConnectionError):
            device.get_current()
        device.reconnect()
        self.assertTrue(device.connected)

    def test_capture_and_failing_notification_providers(self) -> None:
        email = CaptureEmailProvider()
        email.send("test@example.com", "high")
        self.assertEqual(email.calls[0]["type"], "EMAIL")
        with self.assertRaises(RuntimeError):
            FailingNotificationProvider().send("x", "y")


if __name__ == "__main__":
    unittest.main()
