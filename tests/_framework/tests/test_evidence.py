from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._framework.evidence import EvidenceError, EvidenceRun, file_record
from tests._framework.models import (
    EvidenceCredit,
    TestResult as ResultRecord,
    TestStatus as Status,
)
from tests._framework.reporting import verify_run


def sample_result(run_id: str) -> ResultRecord:
    return ResultRecord(
        schema_version=1,
        run_id=run_id,
        test_id="BLE-005",
        profile="unit",
        status=Status.PASS,
        evidence_credit=EvidenceCredit.FULL,
        started_at_utc="2026-09-11T00:00:00.000Z",
        ended_at_utc="2026-09-11T00:00:01.000Z",
        duration_seconds=1.0,
        executor={"display_name": "Tester", "identity": "tester"},
        requirements=[
            {
                "jira": "SCRUM-506",
                "uid": "INT-MLR-407",
                "status": "PASS",
                "credit": "FULL",
            }
        ],
        lifecycle=[
            {
                "stage": stage,
                "started_at_utc": "2026-09-11T00:00:00.000Z",
                "ended_at_utc": "2026-09-11T00:00:00.001Z",
                "outcome": "completed",
            }
            for stage in ("DISCOVER", "VALIDATE", "TEARDOWN", "PUBLISH")
        ],
    )


class EvidenceTests(unittest.TestCase):
    def test_attachment_hash_and_immutable_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_id = "unit-run-001"
            run = EvidenceRun(root, run_id)
            attachment = run.test_path("BLE-005") / "attachments" / "output.log"
            attachment.parent.mkdir(parents=True)
            attachment.write_text("hello", encoding="utf-8")
            run.write_result(sample_result(run_id))
            final = run.finalize({"schema_version": 1, "run_id": run_id})
            self.assertEqual(verify_run(final), [])
            run_record = json.loads(
                (final / "run.json").read_text(encoding="utf-8")
            )
            self.assertRegex(run_record["evidence_manifest_sha256"], r"^[0-9a-f]{64}$")
            with self.assertRaises(EvidenceError):
                EvidenceRun(root, run_id)

    def test_integrity_check_detects_modified_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_id = "unit-run-002"
            run = EvidenceRun(root, run_id)
            attachment = run.test_path("BLE-005") / "attachments" / "output.log"
            attachment.parent.mkdir(parents=True)
            attachment.write_text("before", encoding="utf-8")
            run.write_result(sample_result(run_id))
            final = run.finalize({"schema_version": 1, "run_id": run_id})
            (final / "tests" / "BLE-005" / "attachments" / "output.log").write_text(
                "after", encoding="utf-8"
            )
            self.assertTrue(verify_run(final))

    def test_malformed_result_is_rejected_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = EvidenceRun(Path(temporary), "unit-run-003")
            result = sample_result("unit-run-003")
            result.test_id = "not-a-test-id"
            with self.assertRaisesRegex(EvidenceError, "schema validation"):
                run.write_result(result)


if __name__ == "__main__":
    unittest.main()
