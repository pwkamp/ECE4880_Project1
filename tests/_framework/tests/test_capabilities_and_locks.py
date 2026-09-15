from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._framework.capabilities import check_capability
from tests._framework.models import (
    EvidenceCredit,
    Profile,
    RequirementRef,
    TestManifest as ManifestRecord,
)
from tests._framework.planning import plan_tests
from tests._framework.resource_locks import (
    ResourceBusyError,
    ResourceLockSet,
    _pid_is_alive,
)


def manifest_with(profile: Profile) -> ManifestRecord:
    folder = Path("test")
    return ManifestRecord(
        schema_version=1,
        test_id="BLE-005",
        name="demo",
        folder=folder,
        entrypoint=folder / "test_ble_005.py",
        owners=["integration"],
        requirements=[RequirementRef("SCRUM-506", "INT-MLR-407")],
        profiles={profile.name: profile},
        timeout_seconds=10,
        exclusive_resources=[],
        feasibility="Runnable",
        implementation_status="implemented",
        raw={},
    )


class CapabilityAndLockTests(unittest.TestCase):
    def test_unknown_capability_is_explicitly_unavailable(self) -> None:
        result = check_capability("physical-widget-not-configured")
        self.assertFalse(result.available)
        self.assertIn("not configured", result.detail)

    def test_plan_marks_missing_capability_blocked(self) -> None:
        profile = Profile(
            "unit", "automated", EvidenceCredit.FULL, ["implementation:BLE-005"]
        )
        plan = plan_tests([manifest_with(profile)], "unit")[0]
        self.assertEqual(plan.status.value, "BLOCKED")
        self.assertIn("BLE-005 implementation", plan.reason)

    def test_unsupported_profile_is_skip_not_blocked(self) -> None:
        profile = Profile("unit", "automated", EvidenceCredit.FULL, ["python"])
        plan = plan_tests([manifest_with(profile)], "hil-sim")[0]
        self.assertEqual(plan.status.value, "SKIP")

    def test_manual_profile_is_reported_separately(self) -> None:
        profile = Profile("manual", "manual", EvidenceCredit.PARTIAL, ["python"])
        plan = plan_tests([manifest_with(profile)], "manual")[0]
        self.assertEqual(plan.status.value, "MANUAL_REQUIRED")

    def test_resource_lock_is_exclusive_and_released(self) -> None:
        name = f"runner-unit-{id(self)}"
        first = ResourceLockSet([name])
        second = ResourceLockSet([name])
        first.acquire()
        try:
            with self.assertRaises(ResourceBusyError):
                second.acquire()
        finally:
            first.release()
        second.acquire()
        second.release()

    @unittest.skipUnless(os.name == "nt", "Windows-specific process probe")
    def test_windows_process_probe_does_not_send_ctrl_c(self) -> None:
        with patch(
            "tests._framework.resource_locks.os.kill",
            side_effect=AssertionError("os.kill(pid, 0) sends CTRL_C_EVENT on Windows"),
        ) as kill:
            self.assertTrue(_pid_is_alive(os.getpid()))
        kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
