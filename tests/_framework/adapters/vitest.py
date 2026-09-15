"""Adapter for the PR #1 native Vitest suite."""

from __future__ import annotations

import os
from typing import Sequence

from tests._framework.adapters.native import NativeToolAdapter


class VitestAdapter:
    def __init__(self, native: NativeToolAdapter) -> None:
        self.native = native

    def run_files(self, owner: str, files: Sequence[str], timeout_seconds: float) -> None:
        junit_path = self.native.attachments / f"{owner.lower()}-vitest.xml"
        npm = "npm.cmd" if os.name == "nt" else "npm"
        # PR #1 defines `npm test` as `vitest run`, so only pass file filters and
        # reporter options here. This keeps the runner command reproducible.
        command = [npm, "test", "--", *files, "--reporter=junit", f"--outputFile={junit_path}"]
        self.native.run(f"{owner}-vitest", command, timeout_seconds)
        self.native.run(f"{owner}-frontend-build", [npm, "run", "build"], timeout_seconds)
        self.native.run(f"{owner}-frontend-lint", [npm, "run", "lint"], timeout_seconds)
