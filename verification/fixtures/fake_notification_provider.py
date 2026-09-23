"""Network-free notification providers for deterministic qualification."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CaptureNotificationProvider:
    delivery_type: str
    calls: list[dict[str, object]] = field(default_factory=list)

    def send(self, destination: str, message: str) -> None:
        self.calls.append({"type": self.delivery_type, "destination": destination, "message": message, "timestamp_ns": time.perf_counter_ns()})


class CaptureEmailProvider(CaptureNotificationProvider):
    def __init__(self) -> None:
        super().__init__("EMAIL")


class FailingNotificationProvider:
    def send(self, destination: str, message: str) -> None:
        raise RuntimeError("configured provider failure")
