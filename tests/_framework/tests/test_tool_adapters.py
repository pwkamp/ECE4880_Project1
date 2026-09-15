from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock

from tests._framework.adapters.firmware import FirmwareAdapter
from tests._framework.adapters.pytest_adapter import PytestAdapter
from tests._framework.adapters.vitest import VitestAdapter


class ToolAdapterTests(unittest.TestCase):
    def test_pytest_adapter_requests_junit_and_exact_nodes(self) -> None:
        native = Mock()
        native.attachments = Path("evidence")
        adapter = PytestAdapter(native)
        adapter.run_nodes("BLE-005", ["test_file.py::Case::test_one"], 10)
        command = native.run.call_args.args[1]
        self.assertIn("test_file.py::Case::test_one", command)
        self.assertTrue(any(value.startswith("--junitxml=") for value in command))

    def test_vitest_adapter_uses_native_test_build_and_lint_scripts(self) -> None:
        native = Mock()
        native.attachments = Path("evidence")
        adapter = VitestAdapter(native)
        adapter.run_files("WEB-001", ["src/App.test.tsx"], 10)
        commands = [call.args[1] for call in native.run.call_args_list]
        self.assertEqual(commands[0][1], "test")
        self.assertNotIn("--run", commands[0])
        self.assertIn("src/App.test.tsx", commands[0])
        self.assertEqual(commands[1][1:], ["run", "build"])
        self.assertEqual(commands[2][1:], ["run", "lint"])

    def test_firmware_adapter_targets_the_firmware_project(self) -> None:
        native = Mock()
        adapter = FirmwareAdapter(native)
        adapter.build(30)
        self.assertEqual(
            native.run.call_args.args[1],
            ["idf.py", "-C", "firmware", "build"],
        )


if __name__ == "__main__":
    unittest.main()
