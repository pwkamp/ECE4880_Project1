"""Optional ESP32 UART evidence capture for hardware qualification.

Set ``THERMOMETER_UART_PORT`` (for example ``COM8`` or ``/dev/ttyUSB0``).
The implementation intentionally imports pyserial lazily so software-only
profiles do not gain a hardware dependency.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UartEvent:
    observed_wall_ns: int
    observed_monotonic_ns: int
    line: str


class UartCapture:
    def __init__(self, port: str, baud: int = 115200):
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("pyserial is required; install verification/requirements.txt") from exc
        self._serial: Any = serial.Serial(port=port, baudrate=baud, timeout=0.2)
        self._events: list[UartEvent] = []
        self._queue: queue.Queue[UartEvent] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read, name="verification-uart", daemon=True)
        self._thread.start()

    @classmethod
    def from_environment(cls) -> "UartCapture":
        port = os.environ.get("THERMOMETER_UART_PORT", "").strip()
        if not port:
            raise RuntimeError("THERMOMETER_UART_PORT is not configured")
        baud = int(os.environ.get("THERMOMETER_UART_BAUD", "115200"))
        return cls(port, baud)

    @property
    def events(self) -> list[UartEvent]:
        return list(self._events)

    def _read(self) -> None:
        while not self._stop.is_set():
            raw = self._serial.readline()
            if not raw:
                continue
            event = UartEvent(
                observed_wall_ns=time.time_ns(),
                observed_monotonic_ns=time.perf_counter_ns(),
                line=raw.decode("utf-8", errors="replace").strip(),
            )
            self._events.append(event)
            self._queue.put(event)

    def wait_for(self, fragments: tuple[str, ...], after_wall_ns: int, timeout: float = 2.0) -> UartEvent | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = self._queue.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                return None
            if event.observed_wall_ns >= after_wall_ns and all(fragment in event.line for fragment in fragments):
                return event
        return None

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
        self._serial.close()

    def __enter__(self) -> "UartCapture":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def readiness() -> tuple[bool, str]:
    port = os.environ.get("THERMOMETER_UART_PORT", "").strip()
    if not port:
        return False, "set THERMOMETER_UART_PORT (for example COM8)"
    try:
        import serial  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False, "pyserial is not installed; install verification/requirements.txt"
    return True, f"UART capture configured for {port}"
