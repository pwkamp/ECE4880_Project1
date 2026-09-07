"""Replaceable persistence boundary for the BLE connector service.

The connector deliberately knows nothing about a concrete database driver or
schema migration.  A project-specific adapter can be selected with the
``THERMOMETER_DATABASE_ADAPTER_FACTORY=package.module:create_adapter``
environment variable.  Credentials therefore stay in the database team's
configuration rather than this repository.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


LOGGER = logging.getLogger(__name__)
DATABASE_ADAPTER_FACTORY_ENV = "THERMOMETER_DATABASE_ADAPTER_FACTORY"


@dataclass(frozen=True)
class DeviceIdentity:
    address: str
    name: str


@dataclass(frozen=True)
class SensorReading:
    sensor_id: int
    temperature_c: float | None
    status: str
    display_enabled: bool | None


@dataclass(frozen=True)
class SampleRecord:
    """One database row's worth of live, recovered, or provisional data."""

    device: DeviceIdentity | None
    observed_at_utc: datetime
    boot_id: int | None
    sample_sequence: int | None
    sensor_readings: tuple[SensorReading, ...]
    average_temperature_c: float | None
    source: str
    provisional: bool = False
    failure_reason: str | None = None


@dataclass(frozen=True)
class HistoryBatch:
    device: DeviceIdentity
    boot_id: int
    previous_boot_id: int | None
    new_boot: bool
    samples: tuple[SampleRecord, ...]
    expected_counts: tuple[int, ...]
    retrieved_counts: tuple[int, ...]
    complete: bool
    elapsed_seconds: float
    failure_reason: str | None


@dataclass(frozen=True)
class ConnectionStateRecord:
    device: DeviceIdentity | None
    observed_at_utc: datetime
    phase: str
    connected: bool
    last_seen_utc: datetime | None
    error: str | None
    ready: bool = False
    state_revision: int = 0
    transition_reason: str = ""


@dataclass(frozen=True)
class DisplayStateRecord:
    device: DeviceIdentity
    observed_at_utc: datetime
    sensor_id: int
    requested_enabled: bool
    confirmed_enabled: bool
    visible_state: str


@dataclass(frozen=True)
class PersistenceResult:
    configured: bool
    persisted: bool
    detail: str | None = None


@runtime_checkable
class ThermometerDatabaseAdapter(Protocol):
    """Interface implemented by the database integration teammate."""

    @property
    def persistence_configured(self) -> bool: ...

    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def get_last_boot_id(self, device: DeviceIdentity) -> int | None: ...

    async def publish_current_sample(
        self, sample: SampleRecord
    ) -> PersistenceResult: ...

    async def publish_missing_interval(
        self, sample: SampleRecord
    ) -> PersistenceResult: ...

    async def upsert_history(self, batch: HistoryBatch) -> PersistenceResult: ...

    async def reconcile_provisional_intervals(
        self, batch: HistoryBatch
    ) -> PersistenceResult: ...

    async def publish_connection_state(
        self, state: ConnectionStateRecord
    ) -> PersistenceResult: ...

    async def publish_display_result(
        self, result: DisplayStateRecord
    ) -> PersistenceResult: ...


class NoOpDatabaseAdapter:
    """Development adapter that accepts every write without persisting it."""

    persistence_configured = False

    async def start(self) -> None:
        LOGGER.info("database persistence is disabled; using the no-op adapter")

    async def close(self) -> None:
        return None

    async def get_last_boot_id(self, device: DeviceIdentity) -> int | None:
        return None

    @staticmethod
    def _discard(kind: str) -> PersistenceResult:
        LOGGER.debug("discarded %s because no database adapter is configured", kind)
        return PersistenceResult(False, False, "database adapter is not configured")

    async def publish_current_sample(self, sample: SampleRecord) -> PersistenceResult:
        return self._discard("current sample")

    async def publish_missing_interval(self, sample: SampleRecord) -> PersistenceResult:
        return self._discard("missing interval")

    async def upsert_history(self, batch: HistoryBatch) -> PersistenceResult:
        return self._discard("history batch")

    async def reconcile_provisional_intervals(
        self, batch: HistoryBatch
    ) -> PersistenceResult:
        return self._discard("provisional reconciliation")

    async def publish_connection_state(
        self, state: ConnectionStateRecord
    ) -> PersistenceResult:
        return self._discard("connection state")

    async def publish_display_result(
        self, result: DisplayStateRecord
    ) -> PersistenceResult:
        return self._discard("display result")


def load_database_adapter() -> ThermometerDatabaseAdapter:
    """Load an optional adapter factory without importing database dependencies."""

    factory_path = os.environ.get(DATABASE_ADAPTER_FACTORY_ENV, "").strip()
    if not factory_path:
        return NoOpDatabaseAdapter()

    module_name, separator, factory_name = factory_path.partition(":")
    if not separator or not module_name or not factory_name:
        raise RuntimeError(
            f"{DATABASE_ADAPTER_FACTORY_ENV} must use the form module:factory"
        )
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name, None)
    if factory is None or not callable(factory):
        raise RuntimeError(f"database adapter factory {factory_path!r} is not callable")
    adapter = factory()
    if inspect.isawaitable(adapter):
        raise RuntimeError("the database adapter factory must be synchronous")
    required_methods = (
        "start",
        "close",
        "publish_current_sample",
        "publish_missing_interval",
        "upsert_history",
        "reconcile_provisional_intervals",
        "publish_connection_state",
        "publish_display_result",
    )
    if not all(callable(getattr(adapter, name, None)) for name in required_methods):
        raise RuntimeError(
            f"database adapter returned by {factory_path!r} does not implement "
            "ThermometerDatabaseAdapter"
        )
    return adapter
