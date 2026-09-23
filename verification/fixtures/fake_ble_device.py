"""Deterministic protocol fixture; no Bluetooth hardware or wall clock needed."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeBleDevice:
    boot_id: int = 1
    sample_seq: int = 0
    mtu: int = 247
    response_delay_seconds: float = 0.0
    available: bool = True
    connected: bool = True
    protocol_version: int = 2
    sensors: dict[int, dict[str, Any]] = field(default_factory=lambda: {
        1: {"status": "VALID", "temperature_c": 21.5, "display_enabled": False},
        2: {"status": "VALID", "temperature_c": 22.5, "display_enabled": False},
    })
    history: list[dict[str, Any]] = field(default_factory=list)
    fail_commands: set[str] = field(default_factory=set)
    fail_history_chunks: set[int] = field(default_factory=set)
    transactions: list[dict[str, Any]] = field(default_factory=list)

    def _record(self, opcode: str, request: dict[str, Any], response: Any = None) -> None:
        self.transactions.append({"timestamp_ns": time.perf_counter_ns(), "opcode": opcode, "request": request, "response": response})

    def _ready(self, opcode: str) -> None:
        if not self.available or not self.connected:
            raise ConnectionError("fake BLE device unavailable")
        if self.response_delay_seconds:
            time.sleep(self.response_delay_seconds)
        if opcode in self.fail_commands:
            raise RuntimeError(f"configured {opcode} failure")

    def get_current(self) -> dict[str, Any]:
        self._ready("GET_CURRENT")
        valid = [item["temperature_c"] for item in self.sensors.values() if item["status"] == "VALID"]
        result = {"boot_id": self.boot_id, "sample_seq": self.sample_seq, "sensors": self.sensors, "average_c": sum(valid) / 2 if len(valid) == 2 else None, "average_valid": len(valid) == 2}
        self._record("GET_CURRENT", {}, result)
        return result

    def set_display(self, sensor_id: int, enabled: bool) -> dict[str, Any]:
        self._ready("SET_DISPLAY")
        if sensor_id not in (1, 2) or not isinstance(enabled, bool):
            raise ValueError("malformed display command")
        if self.sensors[sensor_id]["status"] != "VALID":
            raise RuntimeError("sensor unavailable")
        self.sensors[sensor_id]["display_enabled"] = enabled
        result = {"sensor_id": sensor_id, "enabled": enabled}
        self._record("SET_DISPLAY", {"sensor_id": sensor_id, "enabled": enabled}, result)
        return result

    def get_history_meta(self) -> dict[str, Any]:
        self._ready("GET_HISTORY_META")
        sequences = [row["sample_seq"] for row in self.history]
        result = {"boot_id": self.boot_id, "count": len(self.history), "oldest_seq": min(sequences) if sequences else None, "newest_seq": max(sequences) if sequences else None}
        self._record("GET_HISTORY_META", {}, result)
        return result

    def get_history_chunk(self, start: int, count: int) -> list[dict[str, Any]]:
        self._ready("GET_HISTORY_CHUNK")
        if start in self.fail_history_chunks:
            raise RuntimeError("configured history chunk failure")
        # Approximate protocol payload capacity, reserving header/prefix bytes.
        maximum = max(1, (self.mtu - 1 - 12) // 8)
        result = [row for row in self.history if row["sample_seq"] >= start][: min(count, maximum)]
        self._record("GET_HISTORY_CHUNK", {"start": start, "count": count, "mtu": self.mtu}, result)
        return result

    def appear(self) -> None:
        self.available = True

    def disappear(self) -> None:
        self.available = False
        self.connected = False

    def reconnect(self) -> None:
        if not self.available:
            raise ConnectionError("not advertising")
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False
