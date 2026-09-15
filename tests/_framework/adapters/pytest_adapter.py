"""Adapter for the existing Python test suite."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from tests._framework.adapters.native import NativeToolAdapter


class PytestAdapter:
    def __init__(self, native: NativeToolAdapter) -> None:
        self.native = native

    def run_nodes(self, owner: str, node_ids: Sequence[str], timeout_seconds: float) -> None:
        if not node_ids:
            raise ValueError(f"no Python tests are mapped to {owner}")
        junit_path = self.native.attachments / f"{owner.lower()}-pytest.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *node_ids,
            f"--junitxml={junit_path}",
        ]
        self.native.run(f"{owner}-pytest", command, timeout_seconds)
