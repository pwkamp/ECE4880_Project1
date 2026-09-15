from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._framework.adapters.native import NativeToolAdapter, NativeToolFailure
from tests._framework.process_supervisor import CommandResult


class NativeAdapterTests(unittest.TestCase):
    def test_success_captures_logs_duration_and_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = NativeToolAdapter(root, root / "attachments", root / "events.jsonl")
            result = CommandResult(
                command=("tool",),
                returncode=0,
                duration_seconds=1.25,
                timed_out=False,
                stdout="ok",
                stderr="",
            )
            with patch(
                "tests._framework.adapters.native.run_command", return_value=result
            ):
                adapter.run("demo tool", ["tool"], 2.0)
            event = json.loads(
                (root / "events.jsonl").read_text(encoding="utf-8").strip()
            )
            self.assertEqual(event["duration_seconds"], 1.25)
            self.assertTrue((root / "attachments" / "demo_tool.stdout.log").is_file())

    def test_failure_is_not_confused_with_a_completed_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = NativeToolAdapter(root, root / "attachments", root / "events.jsonl")
            result = CommandResult(
                command=("tool",),
                returncode=4,
                duration_seconds=0.1,
                timed_out=False,
                stdout="",
                stderr="bad input",
            )
            with patch(
                "tests._framework.adapters.native.run_command", return_value=result
            ):
                with self.assertRaisesRegex(NativeToolFailure, "bad input"):
                    adapter.run("demo", ["tool"], 2.0)

    def test_timeout_raises_timeout_error_after_evidence_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = NativeToolAdapter(root, root / "attachments", root / "events.jsonl")
            result = CommandResult(
                command=("tool",),
                returncode=None,
                duration_seconds=2.0,
                timed_out=True,
                stdout="partial",
                stderr="",
            )
            with patch(
                "tests._framework.adapters.native.run_command", return_value=result
            ):
                with self.assertRaises(TimeoutError):
                    adapter.run("demo", ["tool"], 2.0)
            self.assertTrue((root / "events.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
