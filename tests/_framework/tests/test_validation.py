from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._framework.discovery import discover
from tests._framework.scaffold import check_scaffold
from tests._framework.validation import (
    EXPECTED_LEVEL_COUNTS,
    _normalized_text_sha256,
    discover_unittest_cases,
    validate_catalog,
)


class CatalogValidationTests(unittest.TestCase):
    def test_frozen_catalog_has_complete_one_to_one_traceability(self) -> None:
        report = validate_catalog()
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.test_count, 56)
        self.assertEqual(report.requirement_count, 255)
        self.assertEqual(report.legacy_test_count, 77)

    def test_requirement_level_counts_are_locked(self) -> None:
        lock = json.loads(
            (Path(__file__).resolve().parents[2] / "requirements.lock.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(lock["expected_counts"]["by_level"], EXPECTED_LEVEL_COUNTS)

    def test_frozen_text_hash_is_independent_of_platform_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lf_path = root / "lf.csv"
            crlf_path = root / "crlf.csv"
            lf_path.write_bytes(b"column\nvalue\n")
            crlf_path.write_bytes(b"column\r\nvalue\r\n")

            self.assertEqual(
                _normalized_text_sha256(lf_path),
                _normalized_text_sha256(crlf_path),
            )

    def test_all_generated_folders_are_current(self) -> None:
        self.assertEqual(check_scaffold(), [])

    def test_discovery_ignores_framework_and_results_directories(self) -> None:
        manifests = discover()
        self.assertEqual(len(manifests), 56)
        self.assertFalse(any(item.folder.name.startswith("_") for item in manifests))

    def test_existing_test_discovery_is_ast_based_and_side_effect_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "test_demo.py").write_text(
                "class Demo:\n"
                "    def test_one(self):\n"
                "        raise RuntimeError('must not execute')\n",
                encoding="utf-8",
            )
            cases = discover_unittest_cases(root)
        self.assertEqual(cases, [f"{root.as_posix()}/test_demo.py::Demo::test_one"])


if __name__ == "__main__":
    unittest.main()
