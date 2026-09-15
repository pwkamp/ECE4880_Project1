"""Context fixture exposed to each consolidated pytest entry point."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from tests._framework.adapters.firmware import FirmwareAdapter
from tests._framework.adapters.native import NativeToolAdapter
from tests._framework.adapters.pytest_adapter import PytestAdapter
from tests._framework.adapters.vitest import VitestAdapter
from tests._framework.clocks import utc_now_text
from tests._framework.io import load_data


class TestContext:
    def __init__(self, configuration: Dict[str, Any]) -> None:
        self.configuration = configuration
        self.run_id = configuration["run_id"]
        self.test_id = configuration["test_id"]
        self.profile = configuration["profile"]
        self.seed = int(configuration["seed"])
        self.repository = Path(configuration["repository"])
        self.test_output = Path(configuration["test_output"])
        self.attachments = self.test_output / "attachments"
        self.events_path = self.test_output / "events.jsonl"
        self.native = NativeToolAdapter(self.repository, self.attachments, self.events_path)
        self.pytest = PytestAdapter(self.native)
        self.vitest = VitestAdapter(self.native)
        self.firmware = FirmwareAdapter(self.native)

    @classmethod
    def from_environment(cls) -> "TestContext":
        path = os.environ.get("THERMOMETER_TEST_CONTEXT")
        if not path:
            raise RuntimeError("THERMOMETER_TEST_CONTEXT was not supplied by tests.runner")
        return cls(load_data(Path(path)))

    def _event(self, event_type: str, **values: Any) -> None:
        self.test_output.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"schema_version": 1, "type": event_type, "captured_at_utc": utc_now_text(), **values}) + "\n")

    def record_assertion(self, name: str, passed: bool, detail: str) -> None:
        self._event("assertion", name=name, passed=passed, detail=detail)
        if not passed:
            raise AssertionError(f"{name}: {detail}")

    def run_existing_python_tests(self, owner: Optional[str] = None) -> None:
        owner = owner or self.test_id
        mapping = load_data(self.repository / "tests" / "_shared" / "existing_python_tests.json")
        nodes = list(mapping["owners"].get(owner, []))
        self.pytest.run_nodes(owner, nodes, float(self.configuration["timeout_seconds"]) * 0.9)

    def run_pr1_vitest(self, owner: Optional[str] = None) -> None:
        owner = owner or self.test_id
        mapping = load_data(self.repository / "tests" / "_shared" / "pr1_vitest_suites.json")
        files = list(mapping["owners"].get(owner, []))
        if not files:
            raise ValueError(f"no PR #1 Vitest files are mapped to {owner}")
        self.vitest.run_files(owner, files, float(self.configuration["timeout_seconds"]) * 0.8)

    def run_c_protocol_vectors(self) -> None:
        compiler = (
            shutil.which("cc")
            or shutil.which("clang")
            or shutil.which("gcc")
            or shutil.which("cl")
        )
        if compiler is None:
            raise RuntimeError("no C compiler is available for protocol vectors")
        source = self.repository / "tests" / "_shared" / "protocol_vectors" / "verify_vectors.c"
        executable = self.attachments / (
            "verify-vectors.exe" if os.name == "nt" else "verify-vectors"
        )
        if Path(compiler).name.lower() in {"cl", "cl.exe"}:
            compile_command = [compiler, "/nologo", str(source), f"/Fe:{executable}"]
        else:
            compile_command = [compiler, str(source), "-o", str(executable)]
        timeout = float(self.configuration["timeout_seconds"]) * 0.3
        self.native.run("protocol-vectors-c-compile", compile_command, timeout)
        self.native.run("protocol-vectors-c-run", [str(executable)], timeout)

    def correlation_id(self, label: str) -> str:
        payload = f"{self.run_id}:{self.test_id}:{label}:{self.seed}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:24]
