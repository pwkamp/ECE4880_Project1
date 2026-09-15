"""Run every Python unit test in the repository with one command."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
TEST_DIRECTORY = BACKEND_ROOT / "pc_client" / "tests"


def main() -> int:
    for import_root in (BACKEND_ROOT, REPOSITORY_ROOT):
        root_text = str(import_root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)

    suite = unittest.defaultTestLoader.discover(
        str(TEST_DIRECTORY),
        pattern="test_*.py",
        top_level_dir=str(BACKEND_ROOT),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
