"""ESP-IDF build and future Unity adapter."""

from __future__ import annotations

from pathlib import Path

from tests._framework.adapters.native import NativeToolAdapter


class FirmwareAdapter:
    def __init__(self, native: NativeToolAdapter) -> None:
        self.native = native

    def build(self, timeout_seconds: float) -> None:
        idf = "idf.py"
        command = [idf, "-C", "firmware", "build"]
        self.native.run("esp-idf-build", command, timeout_seconds)

    def unity(self, test_app: Path, timeout_seconds: float) -> None:
        command = ["idf.py", "-C", str(test_app), "build"]
        self.native.run("esp-idf-unity-build", command, timeout_seconds)
