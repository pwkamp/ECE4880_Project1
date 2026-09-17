"""Run the real BLE service against a simulated thermometer, no ESP32 required.

Exercises the actual polling/persistence pipeline (ThermometerBleService ->
SampleRecord -> the configured database adapter) with a fake BLE client
standing in for the third box, so SCRUM-368/341 can be demoed and reviewed
without hardware. Set THERMOMETER_DATABASE_ADAPTER_FACTORY (see
mysql_adapter.py) before running to actually persist to MySQL; otherwise it
runs against the no-op adapter and just prints what would have been written.

    python -m pc_client.mock_run [--duration SECONDS]
    python -m pc_client.mock_run --duration 20 --drop-after 8 --drop-for 4

--drop-after/--drop-for simulate a dropped poll so the PROVISIONAL /
publish_missing_interval write path can be checked against a real database
too, not just the LIVE happy path.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time
from types import SimpleNamespace

from .ble_service import ThermometerBleService
from .database_adapter import load_database_adapter
from .protocol import CurrentSnapshot, DisplayResult, HistoryChunk, HistoryMeta, SensorSnapshot, VisibleState
from .thermometer_client import DiscoveredThermometer

LOGGER = logging.getLogger("mock_run")

MOCK_DEVICE = DiscoveredThermometer(
    "Mock-Thermometer-01", "AA:BB:CC:DD:EE:00", object(), -40
)
MOCK_PASSKEY = "012345"


class _InMemoryCredentials:
    """Minimal CredentialRegistry stand-in: pre-enrolled, nothing touches disk.

    ble_service.py only reads `.pairing_passkey` off whatever lookup()
    returns, so a duck-typed SimpleNamespace is enough (same approach the
    test suite's FakeCredentials uses).
    """

    def __init__(self) -> None:
        self._records: dict[str, SimpleNamespace] = {}

    def enroll(self, address: str, passkey: str, device_name: str) -> None:
        self._records[address.lower()] = SimpleNamespace(
            pairing_passkey=passkey, device_name=device_name
        )

    def lookup(self, address: str) -> SimpleNamespace | None:
        return self._records.get(address.lower())

    def save_verified(
        self, address: str, device_name: str, passkey: str, **_kwargs
    ) -> None:
        self._records[address.lower()] = SimpleNamespace(
            pairing_passkey=passkey, device_name=device_name
        )

    def delete(self, address: str) -> bool:
        return self._records.pop(address.lower(), None) is not None


class MockBleClient:
    """Stands in for ThermometerBleClient: a slow random walk around 21C.

    A module-level failure window (set via --drop-after/--drop-for) makes
    get_current() raise for a stretch, so the missing-interval/PROVISIONAL
    write path (_publish_missing_interval) can be exercised against a real
    database instead of only against mocks in unit tests.
    """

    failure_window: tuple[float, float] | None = None

    def __init__(self, _target) -> None:
        self.is_connected = False
        self.boot_id = random.getrandbits(32)
        self.sequence = 0
        self._temps = [20.0, 22.0]
        self.disconnected_callback = None

    def set_disconnected_callback(self, callback) -> None:
        self.disconnected_callback = callback

    async def connect(self, *_args, **_kwargs) -> None:
        self.is_connected = True

    async def close(self) -> None:
        self.is_connected = False

    async def pair(self, passkey: str) -> None:
        return None

    async def authenticate(self, passkey: str) -> None:
        return None

    async def request_bond_reset(self) -> None:
        return None

    async def forget_pairing(self) -> None:
        return None

    async def get_current(self) -> CurrentSnapshot:
        if MockBleClient.failure_window is not None:
            start, end = MockBleClient.failure_window
            now = time.monotonic()
            if start <= now <= end:
                LOGGER.warning("simulating a dropped poll (--drop-after/--drop-for)")
                raise RuntimeError("simulated poll failure")
        self.sequence += 1
        self._temps = [
            max(15.0, min(30.0, t + random.uniform(-0.3, 0.3))) for t in self._temps
        ]
        sensors = tuple(
            SensorSnapshot(i + 1, round(t, 2), VisibleState.ON, True)
            for i, t in enumerate(self._temps)
        )
        average = round(sum(self._temps) / len(self._temps), 2)
        return CurrentSnapshot(self.boot_id, self.sequence, sensors, average)

    async def set_display(self, sensor_id: int, enabled: bool) -> DisplayResult:
        return DisplayResult(
            sensor_id, VisibleState.ON if enabled else VisibleState.OFF, enabled
        )

    async def get_history_meta(self) -> HistoryMeta:
        # No on-device history to recover: SCRUM-369 is out of scope here.
        return HistoryMeta(self.boot_id, self.sequence, (0, 0), (0, 0))

    async def get_history_chunk(
        self, sensor_id: int, start_sequence: int, count: int
    ) -> HistoryChunk:
        return HistoryChunk(sensor_id, start_sequence, ())

    def records_per_chunk(self) -> int:
        return 8


async def _discover(*, timeout: float) -> list[DiscoveredThermometer]:
    return [MOCK_DEVICE]


def _print_event(event: dict) -> None:
    kind = event.get("type")
    if kind == "snapshot":
        snapshot = event["snapshot"]
        temps = [s.temperature_c for s in snapshot.sensors]
        LOGGER.info(
            "poll boot=%s seq=%s sensors=%s avg=%s",
            snapshot.boot_id,
            snapshot.newest_sequence,
            temps,
            snapshot.average_c,
        )
    elif kind == "database_error":
        LOGGER.warning("database error on %s: %s", event["operation"], event["message"])
    elif kind in ("connected", "reconnected", "disconnected"):
        LOGGER.info("connection: %s", kind)


async def main(
    duration: float | None,
    drop_after: float | None = None,
    drop_for: float | None = None,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    if drop_after is not None:
        start = time.monotonic() + drop_after
        MockBleClient.failure_window = (start, start + (drop_for or 3.0))

    database = load_database_adapter()
    if not database.persistence_configured:
        LOGGER.warning(
            "THERMOMETER_DATABASE_ADAPTER_FACTORY is not set; running against the "
            "no-op adapter, nothing will be written to MySQL. See mysql_adapter.py."
        )

    credentials = _InMemoryCredentials()
    credentials.enroll(MOCK_DEVICE.address, MOCK_PASSKEY, MOCK_DEVICE.name)

    service = ThermometerBleService(
        database=database,
        client_factory=MockBleClient,
        discover=_discover,
        auto_discover_on_start=True,
        event_handler=_print_event,
        credential_registry=credentials,
    )

    await service.start()
    LOGGER.info("mock service started; polling at 1 Hz, Ctrl+C to stop")
    try:
        if duration is None:
            await asyncio.Event().wait()
        else:
            await asyncio.sleep(duration)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        LOGGER.info("stopping")
        await service.stop()
        await database.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="stop after this many seconds (default: run until Ctrl+C)",
    )
    parser.add_argument(
        "--drop-after",
        type=float,
        default=None,
        help="simulate a dropped BLE poll starting this many seconds in "
        "(exercises publish_missing_interval / PROVISIONAL rows)",
    )
    parser.add_argument(
        "--drop-for",
        type=float,
        default=None,
        help="how long the simulated drop lasts, in seconds (default: 3.0)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        asyncio.run(main(args.duration, args.drop_after, args.drop_for))
    except KeyboardInterrupt:
        pass
