from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tests._framework.cli import main


class CliTests(unittest.TestCase):
    def test_plan_filters_by_component_and_evidence_credit(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "plan",
                    "--profile",
                    "unit",
                    "--changed-component",
                    "integration",
                    "--credit",
                    "PARTIAL",
                    "--all",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("BLE-005", output.getvalue())
        self.assertNotIn("CON-001", output.getvalue())

    def test_pr_profile_requires_exact_source_identity(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error):
            exit_code = main(
                [
                    "run",
                    "--profile",
                    "cross-language",
                    "--test",
                    "BLE-005",
                    "--executor",
                    "Unit Tester",
                ]
            )
        self.assertEqual(exit_code, 2)
        self.assertIn("--source-kind pr or integration", error.getvalue())


if __name__ == "__main__":
    unittest.main()
