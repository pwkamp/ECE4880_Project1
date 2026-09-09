"""Production connection controller built on the low-level BLE client.

Only this class owns a ``ThermometerBleClient``.  HTTP and Tk callers submit
intent to the controller; they never issue GATT requests themselves.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Coroutine, TypedDict

from .database_adapter import (
    ConnectionStateRecord,
    DeviceIdentity,
    DisplayStateRecord,
    HistoryBatch,
    NoOpDatabaseAdapter,
    PersistenceResult,
    SampleRecord,
    SensorReading,
    ThermometerDatabaseAdapter,
)
from .credential_registry import CredentialRegistry
from .ble_scheduler import BleRequestScheduler, RequestPriority
from .persistence_worker import PersistenceWorker
from .history_sync import HistorySynchronizer
from .protocol import (
    CONFIG,
    CurrentSnapshot,
    DataStatus,
    DisplayResult,
    ProtocolError,
    ServiceConfig,
    Status,
    validate_passkey,
)
from .thermometer_client import (
    DiscoveredThermometer,
    HistorySync,
    ThermometerBleClient,
    TimedHistoryRecord,
    describe_ble_error,
    display_name,
)
from .service_state import (
    ConnectionPhase,
    ControllerState,
    CredentialState,
    LifecycleEvent,
    LifecycleEventType,
    transition_state,
)


LOGGER = logging.getLogger(__name__)
_UNCHANGED = object()


class ServiceEvent(TypedDict, total=False):
    type: str
    message: str
    operation: str
    devices: list[DiscoveredThermometer]
    snapshot: CurrentSnapshot
    history: HistorySync
    result: DisplayResult
    status: "ServiceStatus"


EventHandler = Callable[[ServiceEvent], Any]


class ServiceError(RuntimeError):
    """Base class for errors that map cleanly to an API response."""


class ServiceConflictError(ServiceError):
    pass


class ServiceUnavailableError(ServiceError):
    pass


class AuthenticationRequiredError(ServiceError):
    pass


class DisplayTimeoutError(ServiceError):
    pass


class OperationNotFoundError(ServiceError):
    pass


class OperationState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class CurrentDiagnostic:
    available: bool
    received_at_utc: datetime | None
    snapshot: CurrentSnapshot | None
    error: str | None = None


@dataclass(frozen=True)
class ConfirmedDisplayResult:
    result: DisplayResult
    observed_at_utc: datetime
    persistence: PersistenceResult


@dataclass
class TrackedOperation:
    operation_id: str
    kind: str
    state: OperationState
    created_at_utc: datetime
    updated_at_utc: datetime
    progress: float = 0.0
    persistence_configured: bool = False
    persistence_succeeded: bool | None = None
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None


@dataclass(frozen=True)
class ServiceStatus:
    phase: ConnectionPhase
    desired_connected: bool
    target: DeviceIdentity | None
    connected: bool
    ready: bool
    credential_state: CredentialState
    state_revision: int
    state_changed_at_utc: datetime
    transition_reason: str
    retry_count: int
    next_retry_at_utc: datetime | None
    last_seen_utc: datetime | None
    last_error: str | None
    last_database_error: str | None
    protocol_version: int
    persistence_configured: bool
    active_operation_ids: tuple[str, ...]
    manager_running: bool = False
    attempt_id: int = 0
    next_action_at_utc: datetime | None = None
    persistence_pending: int = 0
    persistence_capacity: int = 0
    persistence_overflow_count: int = 0


class ThermometerBleService:
    """Own the BLE link, polling cadence, history recovery, and persistence."""

    def __init__(
        self,
        *,
        database: ThermometerDatabaseAdapter | None = None,
        client_factory: Callable[[Any], ThermometerBleClient] = ThermometerBleClient,
        discover: Callable[..., Awaitable[list[DiscoveredThermometer]]] | None = None,
        event_handler: EventHandler | None = None,
        auto_discover_on_start: bool = True,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        settings: ServiceConfig | None = None,
        credential_registry: CredentialRegistry | None = None,
    ) -> None:
        self.database = database or NoOpDatabaseAdapter()
        self._client_factory = client_factory
        self._discover = discover or ThermometerBleClient.discover
        self._event_handler = event_handler
        self._auto_discover_on_start = auto_discover_on_start
        self._monotonic = monotonic
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep
        self.settings = settings or CONFIG.service
        self.credentials = credential_registry or CredentialRegistry()

        self._started = False
        now = self._utc_now()
        self._state = ControllerState(
            ConnectionPhase.STOPPED,
            False,
            None,
            False,
            False,
            CredentialState.MISSING,
            0,
            None,
            None,
            None,
            0,
            now,
            "service created",
        )
        self._target_generation = 0
        # Verifying an existing Windows bond opens a temporary WinRT
        # BluetoothLEDevice. Repeating that immediately before every reconnect
        # can race Windows while it is releasing the previous GATT session.
        # Remember only what this process has already verified; application
        # authentication and protocol checks still run for every connection.
        self._verified_bond_address: str | None = None
        self._connection_attempt_id = 0
        self._target_passkey: str | None = None
        self._credential_from_registry = False
        self._known_devices: dict[str, DiscoveredThermometer] = {}
        self._client: ThermometerBleClient | None = None
        self._last_current = CurrentDiagnostic(False, None, None)
        self._last_boot_id: int | None = None
        self._history_previous_boot_id: int | None = None
        self._history_is_new_boot = False
        self._last_database_error: str | None = None
        self._database_errors: dict[str, str] = {}

        self._scheduler = BleRequestScheduler(lambda: self.is_ready)
        self._persistence = PersistenceWorker(
            self._database_call,
            configured=lambda: self.database.persistence_configured,
            capacity=self.settings.persistence_queue_capacity,
        )
        self._history_synchronizer = HistorySynchronizer(
            settings=lambda: self.settings,
            monotonic=self._monotonic,
            utc_now=self._utc_now,
            sleep=self._sleep,
            client=self._required_client,
            submit=self._submit_ble,
            current_anchor=lambda: (
                self._last_current.snapshot,
                self._last_current.received_at_utc,
            ),
            publish_current=self._publish_current_snapshot,
        )
        self._manager_events: asyncio.Queue[LifecycleEvent] = asyncio.Queue()
        self._pending_discovery: tuple[DiscoveredThermometer, ...] | None = None
        self._scan_lock = asyncio.Lock()
        self._scan_task: asyncio.Task[list[DiscoveredThermometer]] | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._manager_task: asyncio.Task[None] | None = None
        self._connection_attempt_task: (
            asyncio.Task[CurrentSnapshot | None] | None
        ) = None
        self._poll_task: asyncio.Task[None] | None = None
        self._state_publisher_task: asyncio.Task[None] | None = None
        self._state_publish_queue: asyncio.Queue[ControllerState] = asyncio.Queue()
        self._history_task: asyncio.Task[HistorySync] | None = None
        self._history_operation_id: str | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()

        self._operations: dict[str, TrackedOperation] = {}
        self._operation_events: dict[str, asyncio.Event] = {}
        self._pending_connect_operation_id: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._state.connected

    @property
    def is_ready(self) -> bool:
        return self._state.ready

    @property
    def _phase(self) -> ConnectionPhase:
        return self._state.phase

    @property
    def _desired_connected(self) -> bool:
        return self._state.desired_connected

    @property
    def _target(self) -> DiscoveredThermometer | None:
        return self._state.target

    @property
    def _retry_count(self) -> int:
        return self._state.retry_count

    @property
    def _last_error(self) -> str | None:
        return self._state.last_error

    @property
    def target(self) -> DeviceIdentity | None:
        return self._device_identity(self._target)

    def _transition(
        self,
        phase: ConnectionPhase | None = None,
        *,
        desired_connected: bool | None = None,
        target: DiscoveredThermometer | None | object = _UNCHANGED,
        connected: bool | None = None,
        ready: bool | None = None,
        credential_state: CredentialState | None = None,
        retry_count: int | None = None,
        next_retry_at_utc: datetime | None | object = _UNCHANGED,
        last_seen_utc: datetime | None | object = _UNCHANGED,
        last_error: str | None | object = _UNCHANGED,
        reason: str,
    ) -> None:
        """Atomically publish one internally consistent controller snapshot."""

        previous = self._state
        changes: dict[str, Any] = {}
        optional_changes = {
            "desired_connected": desired_connected,
            "connected": connected,
            "ready": ready,
            "credential_state": credential_state,
            "retry_count": retry_count,
        }
        changes.update(
            (name, value)
            for name, value in optional_changes.items()
            if value is not None
        )
        sentinel_changes = {
            "target": target,
            "next_retry_at_utc": next_retry_at_utc,
            "last_seen_utc": last_seen_utc,
            "last_error": last_error,
        }
        changes.update(
            (name, value)
            for name, value in sentinel_changes.items()
            if value is not _UNCHANGED
        )
        self._state = transition_state(
            previous,
            self._utc_now(),
            phase=phase,
            reason=reason,
            **changes,
        )
        LOGGER.info(
            "BLE state %s -> %s (revision=%d, reason=%s)",
            previous.phase.value,
            self._state.phase.value,
            self._state.revision,
            reason,
        )

    def _make_client(self, target: Any) -> ThermometerBleClient:
        client = self._client_factory(target)
        setter = getattr(client, "set_disconnected_callback", None)
        if setter is not None:
            setter(self._on_transport_disconnected)
        return client

    def _on_transport_disconnected(self, client: ThermometerBleClient) -> None:
        loop = self._event_loop
        if loop is None or loop.is_closed():
            return

        def notify_manager() -> None:
            if (
                not self._started
                or self._state.phase is ConnectionPhase.DISCONNECTING
                or self._client is not client
            ):
                return
            self._post_manager_event(
                LifecycleEventType.LINK_LOST,
                "BLE session ended unexpectedly",
                client,
            )

        loop.call_soon_threadsafe(notify_manager)

    async def start(self) -> None:
        if self._started:
            return
        self._event_loop = asyncio.get_running_loop()
        self._started = True
        self._manager_events = asyncio.Queue()
        self._pending_discovery = None
        self._transition(
            (
                ConnectionPhase.DISCOVERING
                if self._auto_discover_on_start
                else ConnectionPhase.DISCONNECTED
            ),
            desired_connected=self._auto_discover_on_start,
            connected=False,
            ready=False,
            credential_state=CredentialState.MISSING,
            retry_count=0,
            next_retry_at_utc=None,
            last_error=None,
            reason="service started",
        )
        try:
            await self.database.start()
        except Exception as exc:
            self._last_database_error = describe_ble_error(exc)
            self._database_errors["start"] = self._last_database_error
            LOGGER.exception("database adapter failed to start")

        self._scheduler.start()
        self._persistence.start()
        self._state_publisher_task = asyncio.create_task(
            self._state_publisher(), name="thermometer-state-publisher"
        )
        self._manager_task = asyncio.create_task(
            self._supervise_connection_manager(),
            name="thermometer-connection-manager-supervisor",
        )
        self._poll_task = asyncio.create_task(
            self._poll_current(), name="thermometer-current-poller"
        )
        self._post_manager_event(LifecycleEventType.START, "service started")
        await self._publish_connection_state()

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self._transition(
            ConnectionPhase.DISCONNECTING,
            desired_connected=False,
            ready=False,
            next_retry_at_utc=None,
            reason="service stopping",
        )
        self._post_manager_event(LifecycleEventType.STOP, "service stopping")
        if self._pending_connect_operation_id:
            self._cancel_operation(
                self._pending_connect_operation_id, "service stopped"
            )
            self._pending_connect_operation_id = None
        await self._cancel_history("service stopped")

        for task in (self._manager_task, self._poll_task):
            if task is not None:
                task.cancel()
        for task in tuple(self._background_tasks):
            task.cancel()
        await asyncio.gather(
            *(task for task in (self._manager_task, self._poll_task) if task),
            *tuple(self._background_tasks),
            return_exceptions=True,
        )
        self._manager_task = None
        self._poll_task = None
        self._background_tasks.clear()

        await self._close_client()
        await self._scheduler.stop(ServiceUnavailableError("service stopped"))

        self._transition(
            ConnectionPhase.STOPPED,
            connected=False,
            ready=False,
            reason="service stopped",
        )
        await self._publish_connection_state()
        if self._state_publisher_task is not None:
            try:
                await asyncio.wait_for(self._state_publish_queue.join(), timeout=1.0)
            except asyncio.TimeoutError:
                LOGGER.warning("timed out flushing connection-state publications")
            self._state_publisher_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._state_publisher_task
            self._state_publisher_task = None
        await self._persistence.stop()
        try:
            await self.database.close()
        except Exception:
            LOGGER.exception("database adapter failed to close")

    async def scan(self) -> list[DiscoveredThermometer]:
        if self.is_connected or self._phase in {
            ConnectionPhase.PAIRING,
            ConnectionPhase.CONNECTING,
            ConnectionPhase.VERIFYING,
            ConnectionPhase.CONNECTED,
            ConnectionPhase.RECONNECTING,
            ConnectionPhase.DISCONNECTING,
        }:
            raise ServiceConflictError("cannot scan while a BLE connection is active")
        discovery_generation = self._target_generation
        try:
            devices = await self._scan_for_devices(
                self.settings.startup_scan_timeout_seconds
            )
            # Manual discovery is an input to the same lifecycle queue used by
            # automatic discovery. It can never be required to unstick it.
            if (
                discovery_generation == self._target_generation
                and self._target is None
            ):
                self._pending_discovery = tuple(devices)
                self._post_manager_event(
                    LifecycleEventType.DISCOVERY_RESULT,
                    "manual discovery completed",
                    tuple(devices),
                    generation=discovery_generation,
                )
            return devices
        except Exception as exc:
            raise ServiceUnavailableError(
                f"BLE discovery failed: {describe_ble_error(exc)}"
            ) from exc

    async def connect(
        self,
        target: str | DiscoveredThermometer | Any,
        passkey: str | None = None,
    ) -> TrackedOperation:
        return await self._begin_connection(target, passkey, "connect")

    async def pair(
        self,
        target: str | DiscoveredThermometer | Any,
        passkey: str | None = None,
    ) -> TrackedOperation:
        # Pairing is enrollment: the credential is saved only after the full
        # protected protocol has been verified.
        return await self._begin_connection(target, passkey, "pair")

    async def _begin_connection(
        self,
        target: str | DiscoveredThermometer | Any,
        passkey: str | None,
        operation_kind: str,
    ) -> TrackedOperation:
        selected = self._resolve_target(target)
        current_address = self._target.address.lower() if self._target else None
        supplied_passkey = validate_passkey(passkey) if passkey is not None else None
        credential = supplied_passkey
        from_registry = False
        if credential is None:
            stored = self.credentials.lookup(selected.address)
            if stored is not None:
                credential = stored.pairing_passkey
                from_registry = True

        if self.is_ready and current_address == selected.address.lower():
            operation = self._new_operation(operation_kind)
            self._succeed_operation(
                operation,
                {"address": selected.address, "already_connected": True},
            )
            return operation

        if credential is None:
            self._target_generation += 1
            self._transition(
                ConnectionPhase.AUTHENTICATION_REQUIRED,
                desired_connected=True,
                target=selected,
                connected=False,
                ready=False,
                credential_state=CredentialState.MISSING,
                next_retry_at_utc=None,
                last_error="a six-digit passkey is required to enroll this device",
                reason="device credential is not enrolled",
            )
            await self._publish_connection_state()
            raise AuthenticationRequiredError(
                "a six-digit passkey is required to enroll this device"
            )

        operation = self._new_operation(operation_kind)
        if self._pending_connect_operation_id:
            self._cancel_operation(
                self._pending_connect_operation_id, "superseded by another connect request"
            )
        self._pending_connect_operation_id = operation.operation_id
        operation.state = OperationState.RUNNING
        operation.updated_at_utc = self._utc_now()

        if self.is_connected and current_address != selected.address.lower():
            self._transition(
                ConnectionPhase.DISCONNECTING,
                ready=False,
                reason="switching selected thermometer",
            )
            await self._cancel_history("target changed")
            await self._close_client()
        self._target_generation += 1
        self._target_passkey = credential
        self._credential_from_registry = from_registry
        self._known_devices[selected.address.lower()] = selected
        self._transition(
            ConnectionPhase.PAIRING,
            desired_connected=True,
            target=selected,
            connected=False,
            ready=False,
            credential_state=CredentialState.AVAILABLE,
            next_retry_at_utc=None,
            last_error=None,
            reason=f"{operation_kind} requested",
        )
        self._post_manager_event(
            LifecycleEventType.INTENT_CHANGED, f"{operation_kind} requested"
        )
        await self._publish_connection_state()
        return operation

    async def reconnect(self) -> TrackedOperation:
        if self._target is None:
            raise ServiceConflictError("no device has been selected in this process")
        return await self.connect(self._target)

    async def disconnect(self) -> None:
        # Service invariant: only an explicit caller action suppresses reconnects.
        self._target_generation += 1
        self._transition(
            ConnectionPhase.DISCONNECTING,
            desired_connected=False,
            ready=False,
            next_retry_at_utc=None,
            reason="explicit disconnect requested",
        )
        self._post_manager_event(
            LifecycleEventType.INTENT_CHANGED, "explicit disconnect requested"
        )
        await self._cancel_history("explicitly disconnected")
        if (
            self._connection_attempt_task is not None
            and not self._connection_attempt_task.done()
        ):
            self._connection_attempt_task.cancel()
            await asyncio.gather(
                self._connection_attempt_task, return_exceptions=True
            )
        await self._close_client()
        self._last_current = CurrentDiagnostic(
            False, self._last_current.received_at_utc, None, "explicitly disconnected"
        )
        self._transition(
            ConnectionPhase.DISCONNECTED,
            connected=False,
            ready=False,
            reason="explicitly disconnected",
        )
        if self._pending_connect_operation_id:
            self._cancel_operation(
                self._pending_connect_operation_id, "explicitly disconnected"
            )
            self._pending_connect_operation_id = None
        await self._publish_connection_state()
        await self._emit({"type": "disconnected"})

    async def forget_pairing(
        self, target: str | DiscoveredThermometer | Any
    ) -> TrackedOperation:
        selected = self._resolve_target(target)
        if (
            not self.is_ready
            or self._target is None
            or self._target.address.lower() != selected.address.lower()
        ):
            raise ServiceConflictError(
                "an authenticated connection to this device is required to reset its bond"
            )
        self._target_generation += 1
        self._transition(
            ConnectionPhase.DISCONNECTING,
            desired_connected=False,
            target=selected,
            ready=False,
            reason="authorized pairing reset requested",
        )
        self._notify_connection_manager()
        await self._cancel_history("pairing reset")

        async def perform() -> dict[str, Any]:
            client = self._required_client()
            reset_stage = "ESP32 authorization"
            try:
                await client.request_bond_reset()
                reset_stage = "BLE disconnection"
                await self._close_client()
                reset_stage = "Windows bond removal"
                # Be conservative if Windows reports a partial unpair: force
                # the next connection to verify the bond again.
                self._verified_bond_address = None
                await client.forget_pairing()
                reset_stage = "credential registry removal"
                self.credentials.delete(selected.address)
            except Exception as exc:
                await self._close_client()
                message = f"pairing reset failed during {reset_stage}: {describe_ble_error(exc)}"
                self._transition(
                    ConnectionPhase.DISCONNECTED,
                    connected=False,
                    ready=False,
                    last_error=message,
                    reason="pairing reset partially failed",
                )
                await self._publish_connection_state()
                raise RuntimeError(message) from exc

            self._target_passkey = None
            self._credential_from_registry = False
            self._transition(
                ConnectionPhase.DISCONNECTED,
                connected=False,
                ready=False,
                credential_state=CredentialState.MISSING,
                last_error=None,
                reason="pairing reset completed",
            )
            await self._publish_connection_state()
            await self._emit({"type": "pairing_reset"})
            return {"address": selected.address, "forgotten": True}

        await self._publish_connection_state()
        return self._launch_operation("forget_pairing", perform())

    def get_status(self) -> ServiceStatus:
        self._prune_operations()
        return self._status_from_state(self._state)

    def _status_from_state(self, state: ControllerState) -> ServiceStatus:
        active = tuple(
            operation_id
            for operation_id, operation in self._operations.items()
            if operation.state in {OperationState.QUEUED, OperationState.RUNNING}
        )
        persistence_health = self._persistence.health
        return ServiceStatus(
            phase=state.phase,
            desired_connected=state.desired_connected,
            target=self._device_identity(state.target),
            connected=state.connected,
            ready=state.ready,
            credential_state=state.credential_state,
            state_revision=state.revision,
            state_changed_at_utc=state.changed_at_utc,
            transition_reason=state.reason,
            retry_count=state.retry_count,
            next_retry_at_utc=state.next_retry_at_utc,
            last_seen_utc=state.last_seen_utc,
            last_error=state.last_error,
            last_database_error=self._last_database_error,
            protocol_version=CONFIG.protocol_version,
            persistence_configured=self.database.persistence_configured,
            active_operation_ids=active,
            manager_running=(
                self._manager_task is not None and not self._manager_task.done()
            ),
            attempt_id=self._connection_attempt_id,
            next_action_at_utc=state.next_retry_at_utc,
            persistence_pending=persistence_health.pending,
            persistence_capacity=persistence_health.capacity,
            persistence_overflow_count=persistence_health.overflow_count,
        )

    def get_current(self) -> CurrentDiagnostic:
        return self._last_current

    async def set_display(
        self, sensor_id: int, enabled: bool
    ) -> ConfirmedDisplayResult:
        if not 1 <= sensor_id <= CONFIG.device.sensor_count:
            raise ValueError(
                f"sensor_id must be between 1 and {CONFIG.device.sensor_count}"
            )
        if not self.is_ready:
            raise ServiceUnavailableError("thermometer is not connected")

        command_started = self._monotonic()
        command_timeout = self.settings.display_command_timeout_seconds
        try:
            result = await asyncio.wait_for(
                self._submit_ble(
                    RequestPriority.DISPLAY,
                    f"set display {sensor_id}",
                    lambda: self._required_client().set_display(sensor_id, enabled),
                ),
                timeout=command_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise DisplayTimeoutError(
                "the ESP32 did not confirm the display state before the timeout"
            ) from exc

        observed_at = self._utc_now()
        identity = self.target
        assert identity is not None
        database_task = self._persistence.enqueue(
            "publish_display_result",
            DisplayStateRecord(
                identity,
                observed_at,
                sensor_id,
                enabled,
                result.display_enabled,
                result.visible_state.name,
            ),
        )
        remaining = command_timeout - (self._monotonic() - command_started)
        try:
            persistence = await asyncio.wait_for(
                asyncio.shield(database_task), timeout=max(0.001, remaining)
            )
        except asyncio.TimeoutError:
            self._track_background(database_task)
            persistence = PersistenceResult(
                self.database.persistence_configured,
                False,
                "display result persistence is still pending",
            )
        self._update_cached_display(result)
        await self._emit({"type": "display", "result": result})
        if self._last_current.snapshot is not None:
            await self._emit(
                {"type": "snapshot", "snapshot": self._last_current.snapshot}
            )
        return ConfirmedDisplayResult(result, observed_at, persistence)

    async def request_history_sync(self) -> TrackedOperation:
        if not self.is_ready:
            raise ServiceUnavailableError("thermometer is not connected")
        return self._start_history_sync("manual")

    def get_operation(self, operation_id: str) -> TrackedOperation:
        self._prune_operations()
        try:
            return self._operations[operation_id]
        except KeyError as exc:
            raise OperationNotFoundError(
                f"operation {operation_id!r} was not found"
            ) from exc

    async def wait_for_operation(
        self, operation_id: str, timeout: float | None = None
    ) -> TrackedOperation:
        operation = self.get_operation(operation_id)
        if operation.state not in {OperationState.QUEUED, OperationState.RUNNING}:
            return operation
        completion = self._operation_events[operation_id]
        if timeout is None:
            await completion.wait()
        else:
            await asyncio.wait_for(completion.wait(), timeout=timeout)
        return self.get_operation(operation_id)

    async def _supervise_connection_manager(self) -> None:
        """Keep the lifecycle worker alive and always retrieve its failures."""

        while self._started:
            try:
                await self._connection_manager()
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                message = f"connection manager failed: {describe_ble_error(exc)}"
                LOGGER.exception(message)
                if not self._desired_connected:
                    phase = ConnectionPhase.DISCONNECTED
                elif self._target is None:
                    phase = ConnectionPhase.DISCOVERING
                else:
                    phase = ConnectionPhase.RECONNECTING
                self._transition(
                    phase,
                    connected=False,
                    ready=False,
                    last_error=message,
                    reason="connection manager recovered from an unexpected failure",
                )
                await self._publish_connection_state()
                await self._sleep(self.settings.auto_discovery_interval_seconds)

    async def _connection_manager(self) -> None:
        while self._started:
            # Lifecycle events are queued, not represented by a lossy Event
            # flag. A device appearing after startup or after a power cycle is
            # therefore observed without an unrelated HTTP request.
            try:
                if not self._desired_connected:
                    if self._phase is not ConnectionPhase.DISCONNECTED:
                        self._transition(
                            ConnectionPhase.DISCONNECTED,
                            connected=False,
                            ready=False,
                            reason="automatic connection is disabled",
                        )
                        await self._publish_connection_state()
                    await self._wait_for_manager_wakeup(None)
                    continue

                if self.is_ready:
                    await self._wait_for_manager_wakeup(
                        self.settings.auto_discovery_interval_seconds
                    )
                    if (
                        self._desired_connected
                        and (
                            self._client is None
                            or not self._client.is_connected
                        )
                    ):
                        await self._connection_lost("BLE session ended unexpectedly")
                    continue

                lifecycle_attempt_started = False
                if self._target is None:
                    self._connection_attempt_id += 1
                    lifecycle_attempt_started = True
                    discovery_generation = self._target_generation
                    self._transition(
                        ConnectionPhase.DISCOVERING,
                        connected=False,
                        ready=False,
                        credential_state=CredentialState.MISSING,
                        next_retry_at_utc=None,
                        last_error=None,
                        reason="running the next automatic discovery probe",
                    )
                    await self._publish_connection_state()
                    devices = await self._next_discovery_observation()
                    if (
                        discovery_generation != self._target_generation
                        or self._target is not None
                    ):
                        # A manual selection/disconnect won while discovery was
                        # in flight; its newer state is authoritative.
                        continue
                    if len(devices) == 1:
                        self._target_generation += 1
                        selected = devices[0]
                        stored = self.credentials.lookup(selected.address)
                        if stored is None:
                            self._target_passkey = None
                            self._credential_from_registry = False
                            self._transition(
                                ConnectionPhase.AUTHENTICATION_REQUIRED,
                                target=selected,
                                connected=False,
                                ready=False,
                                credential_state=CredentialState.MISSING,
                                next_retry_at_utc=None,
                                last_error=None,
                                reason="discovered device requires enrollment",
                            )
                            await self._publish_connection_state()
                            await self._wait_for_manager_wakeup(None)
                            continue
                        self._target_passkey = stored.pairing_passkey
                        self._credential_from_registry = True
                        self._transition(
                            ConnectionPhase.PAIRING,
                            target=selected,
                            connected=False,
                            ready=False,
                            credential_state=CredentialState.AVAILABLE,
                            retry_count=0,
                            next_retry_at_utc=None,
                            last_error=None,
                            reason="registered device discovered",
                        )
                    elif len(devices) > 1:
                        self._transition(
                            ConnectionPhase.SELECTION_REQUIRED,
                            target=None,
                            connected=False,
                            ready=False,
                            retry_count=0,
                            next_retry_at_utc=None,
                            last_error=None,
                            reason="multiple compatible thermometers discovered",
                        )
                        await self._publish_connection_state()
                        await self._wait_for_manager_wakeup(None)
                        continue
                    else:
                        retry_delay = self.settings.auto_discovery_interval_seconds
                        self._transition(
                            ConnectionPhase.DISCOVERING,
                            connected=False,
                            ready=False,
                            next_retry_at_utc=self._utc_now()
                            + timedelta(seconds=retry_delay),
                            reason=(
                                "no compatible thermometer found; "
                                "next probe scheduled"
                            ),
                        )
                        await self._publish_connection_state()
                        await self._wait_for_manager_wakeup(retry_delay)
                        continue

                if self._target_passkey is None:
                    assert self._target is not None
                    if (
                        self._phase is ConnectionPhase.AUTHENTICATION_REQUIRED
                        and self._state.credential_state
                        is CredentialState.REJECTED
                    ):
                        # Unrelated scan or database events must never retry a
                        # credential the ESP32 has already rejected. A caller
                        # must explicitly provide a replacement passkey.
                        await self._wait_for_manager_wakeup(None)
                        continue
                    stored = self.credentials.lookup(self._target.address)
                    if stored is None:
                        self._transition(
                            ConnectionPhase.AUTHENTICATION_REQUIRED,
                            connected=False,
                            ready=False,
                            credential_state=CredentialState.MISSING,
                            reason="device credential is not enrolled",
                        )
                        await self._publish_connection_state()
                        await self._wait_for_manager_wakeup(None)
                        continue
                    self._target_passkey = stored.pairing_passkey
                    self._credential_from_registry = True

                reconnecting = self._phase is ConnectionPhase.RECONNECTING
                assert self._target is not None
                selected_target = self._target
                selected_generation = self._target_generation

                if not lifecycle_attempt_started:
                    self._connection_attempt_id += 1

                if reconnecting:
                    # A BLEDevice object represents a particular Windows
                    # discovery result. After an ESP32 reboot, wait for the
                    # selected address to advertise again and use the fresh
                    # object instead of repeatedly opening the stale one.
                    refreshed_target = await self._find_reconnect_target(
                        selected_target, selected_generation
                    )
                    if refreshed_target is None:
                        continue
                    selected_target = refreshed_target

                connection_attempt = asyncio.create_task(
                    self._open_connection(
                        selected_target,
                        selected_generation,
                        self._target_passkey,
                    ),
                    name="thermometer-connection-attempt",
                )
                self._connection_attempt_task = connection_attempt
                try:
                    snapshot = await connection_attempt
                except asyncio.CancelledError:
                    if not self._started:
                        raise
                    # Explicit disconnect invalidated this attempt. The state
                    # was already committed by the caller; just re-read it.
                    continue
                finally:
                    if self._connection_attempt_task is connection_attempt:
                        self._connection_attempt_task = None
                if snapshot is None:
                    continue
                previous_boot_id = self._last_boot_id
                if previous_boot_id is None:
                    previous_boot_id = await self._read_last_persisted_boot(
                        selected_target
                    )
                self._history_previous_boot_id = previous_boot_id
                self._history_is_new_boot = (
                    previous_boot_id is not None
                    and previous_boot_id != snapshot.boot_id
                )
                self._last_boot_id = snapshot.boot_id
                observed_at = self._utc_now()
                self._last_current = CurrentDiagnostic(True, observed_at, snapshot)
                connected_name = getattr(self._client, "device_name", None)
                if self._has_useful_device_name(
                    connected_name, selected_target.address
                ):
                    selected_target = replace(
                        selected_target, name=connected_name.strip()
                    )
                self.credentials.save_verified(
                    selected_target.address,
                    selected_target.name,
                    self._target_passkey,
                    connected_at_utc=observed_at,
                )
                self._credential_from_registry = True
                self._transition(
                    ConnectionPhase.CONNECTED,
                    target=selected_target,
                    connected=True,
                    ready=True,
                    credential_state=CredentialState.VERIFIED,
                    retry_count=0,
                    next_retry_at_utc=None,
                    last_seen_utc=observed_at,
                    last_error=None,
                    reason="protected protocol verified",
                )
                await self._publish_connection_state()
                self._complete_pending_connect()
                await self._publish_current_snapshot(snapshot, observed_at)
                await self._emit(
                    {"type": "reconnected" if reconnecting else "connected"}
                )
                self._start_history_sync("automatic")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                message = describe_ble_error(exc)
                if not self._desired_connected:
                    await self._close_client()
                    if self._phase is not ConnectionPhase.DISCONNECTED:
                        self._transition(
                            ConnectionPhase.DISCONNECTED,
                            connected=False,
                            ready=False,
                            next_retry_at_utc=None,
                            reason="connection attempt superseded by disconnect",
                        )
                        await self._publish_connection_state()
                    continue
                authentication_failure = (
                    isinstance(exc, ProtocolError)
                    and exc.status
                    in {
                        Status.AUTHENTICATION_REQUIRED,
                        Status.AUTHENTICATION_FAILED,
                        Status.AUTHENTICATION_LOCKED,
                    }
                )
                if authentication_failure:
                    self._target_passkey = None
                    self._credential_from_registry = False
                    self._fail_pending_connect(message)
                    self._transition(
                        ConnectionPhase.AUTHENTICATION_REQUIRED,
                        connected=False,
                        ready=False,
                        credential_state=CredentialState.REJECTED,
                        next_retry_at_utc=None,
                        last_error=message,
                        reason="device rejected the stored or supplied credential",
                    )
                    await self._close_client()
                    await self._publish_connection_state()
                    await self._wait_for_manager_wakeup(None)
                    continue

                retry_delay = self.settings.auto_discovery_interval_seconds
                LOGGER.warning(
                    "BLE connection attempt %d failed; retrying: %s",
                    self._connection_attempt_id,
                    message,
                )
                self._fail_pending_connect(message)
                retry_phase = (
                    ConnectionPhase.DISCOVERING
                    if self._target is None
                    else ConnectionPhase.RECONNECTING
                )
                self._transition(
                    retry_phase,
                    connected=False,
                    ready=False,
                    retry_count=self._retry_count + 1,
                    next_retry_at_utc=self._utc_now()
                    + timedelta(seconds=retry_delay),
                    last_error=message,
                    reason=(
                        "discovery probe failed; next probe scheduled"
                        if retry_phase is ConnectionPhase.DISCOVERING
                        else "connection attempt failed; retry scheduled"
                    ),
                )
                await self._close_client()
                await self._publish_connection_state()
                await self._emit(
                    {
                        "type": (
                            "discovery_error"
                            if retry_phase is ConnectionPhase.DISCOVERING
                            else "connection_lost"
                        ),
                        "message": (
                            f"Discovery unavailable; retrying automatically: {message}"
                            if retry_phase is ConnectionPhase.DISCOVERING
                            else f"Connection unavailable; retrying automatically: {message}"
                        ),
                    }
                )
                await self._wait_for_manager_wakeup(retry_delay)

    async def _open_connection(
        self,
        selected_target: DiscoveredThermometer,
        selected_generation: int,
        passkey: str,
    ) -> CurrentSnapshot | None:
        async with self._lifecycle_lock:
            client = self._make_client(selected_target.device)
            normalized_address = selected_target.address.casefold()
            recovery_deadline = (
                self._monotonic() + self.settings.recovery_deadline_seconds
                if self._credential_from_registry
                else None
            )

            def step_timeout(maximum: float) -> float:
                if recovery_deadline is None:
                    return maximum
                remaining = recovery_deadline - self._monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError(
                        "connection recovery exceeded its end-to-end deadline"
                    )
                return min(maximum, remaining)

            try:
                if self._verified_bond_address != normalized_address:
                    self._transition(
                        ConnectionPhase.PAIRING,
                        connected=False,
                        ready=False,
                        credential_state=CredentialState.AVAILABLE,
                        next_retry_at_utc=None,
                        reason="ensuring authenticated Windows bond",
                    )
                    await self._publish_connection_state()
                    await self._run_connection_step(
                        "Windows pairing verification",
                        step_timeout(CONFIG.client.pairing_timeout_seconds),
                        lambda: client.pair(passkey),
                    )
                    if (
                        not self._desired_connected
                        or selected_generation != self._target_generation
                    ):
                        await self._close_client_instance(client)
                        return None
                    self._verified_bond_address = normalized_address

                self._transition(
                    ConnectionPhase.CONNECTING,
                    connected=False,
                    ready=False,
                    reason="opening GATT transport with process-verified bond",
                )
                await self._publish_connection_state()
                await self._run_connection_step(
                    "GATT connection and service discovery",
                    step_timeout(CONFIG.client.connect_timeout_seconds),
                    lambda: client.connect(
                        passkey,
                        ensure_pairing=False,
                        authenticate=False,
                    ),
                )
                if (
                    not self._desired_connected
                    or selected_generation != self._target_generation
                ):
                    await self._close_client_instance(client)
                    return None
                self._client = client
                self._transition(
                    ConnectionPhase.VERIFYING,
                    connected=True,
                    ready=False,
                    reason="verifying application authentication and protocol",
                )
                await self._publish_connection_state()
                await self._run_connection_step(
                    "application authentication",
                    step_timeout(CONFIG.client.connect_timeout_seconds),
                    lambda: client.authenticate(passkey),
                )
                if (
                    not self._desired_connected
                    or selected_generation != self._target_generation
                ):
                    await self._close_client_instance(client)
                    if self._client is client:
                        self._client = None
                    return None
                # Prove the protected protocol works and publish current data
                # before any history recovery begins.
                snapshot = await self._run_connection_step(
                    "initial protected temperature request",
                    step_timeout(CONFIG.client.connect_timeout_seconds),
                    client.get_current,
                )
            except Exception:
                await self._close_client_instance(client)
                if self._client is client:
                    self._client = None
                raise
            except asyncio.CancelledError:
                await self._close_client_instance(client)
                if self._client is client:
                    self._client = None
                raise
            if (
                not self._desired_connected
                or selected_generation != self._target_generation
            ):
                await self._close_client_instance(client)
                return None
        return snapshot

    async def _run_connection_step(
        self,
        step_name: str,
        timeout: float,
        action: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Bound a device-dependent state so it always has an exit trigger."""

        try:
            return await asyncio.wait_for(action(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise ServiceUnavailableError(
                f"{step_name} timed out after {timeout:g} seconds"
            ) from exc

    async def _connection_lost(
        self, reason: str, *, close_client: bool = True
    ) -> None:
        if not self._state.connected and self._phase in {
            ConnectionPhase.RECONNECTING,
            ConnectionPhase.DISCONNECTED,
        }:
            return
        self._last_current = CurrentDiagnostic(
            False, self._last_current.received_at_utc, None, reason
        )
        self._transition(
            (
                ConnectionPhase.RECONNECTING
                if self._desired_connected
                else ConnectionPhase.DISCONNECTED
            ),
            connected=False,
            ready=False,
            retry_count=(
                max(1, self._retry_count) if self._desired_connected else 0
            ),
            next_retry_at_utc=(
                self._utc_now() if self._desired_connected else None
            ),
            last_error=reason,
            reason="BLE transport disconnected",
        )
        await self._cancel_history("connection lost")
        if close_client:
            await self._close_client()
        await self._publish_connection_state()
        self._notify_connection_manager()

    async def _close_client(self) -> None:
        async with self._lifecycle_lock:
            client, self._client = self._client, None
            if client is not None:
                await self._close_client_instance(client)

    async def _close_client_instance(self, client: Any) -> None:
        """Best-effort cleanup that cannot hold the state machine forever."""

        cleanup_timeout = min(
            CONFIG.client.connect_timeout_seconds,
            self.settings.auto_discovery_interval_seconds,
        )
        try:
            await asyncio.wait_for(client.close(), timeout=cleanup_timeout)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning(
                "BLE client cleanup did not complete: %s", describe_ble_error(exc)
            )

    async def _poll_current(self) -> None:
        # Requirement: SWE-CONN-LLR-501 (SCRUM-536). Absolute monotonic
        # deadlines prevent cumulative drift even when a BLE or database cycle
        # takes longer than usual.
        interval = self.settings.poll_interval_seconds
        monotonic_anchor = self._monotonic()
        utc_anchor = self._utc_now()
        next_deadline = monotonic_anchor + interval
        while self._started:
            await self._sleep(max(0.0, next_deadline - self._monotonic()))
            # Never issue a burst of stale GET_CURRENT transactions after a
            # blocked adapter or OS stall. Preserve each elapsed database slot
            # explicitly, then request only the newest due sample.
            while next_deadline + interval <= self._monotonic():
                missed_at = utc_anchor + timedelta(
                    seconds=next_deadline - monotonic_anchor
                )
                await self._publish_missing_interval(
                    missed_at, "current polling deadline was missed"
                )
                next_deadline += interval
            scheduled_at = utc_anchor + timedelta(
                seconds=next_deadline - monotonic_anchor
            )
            if self.is_ready:
                try:
                    snapshot = await self._submit_ble(
                        RequestPriority.CURRENT,
                        "scheduled current sample",
                        lambda: self._required_client().get_current(),
                    )
                    await self._publish_current_snapshot(snapshot, self._utc_now())
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    message = describe_ble_error(exc)
                    await self._publish_missing_interval(scheduled_at, message)
                    self._post_manager_event(
                        LifecycleEventType.LINK_LOST,
                        message,
                    )
            else:
                await self._publish_missing_interval(
                    scheduled_at, self._last_error or "thermometer is not connected"
                )

            next_deadline += interval
            lag = self._monotonic() - next_deadline
            if lag > self.settings.poll_tolerance_seconds:
                LOGGER.warning("current polling is %.3f seconds behind schedule", lag)

    async def _submit_ble(
        self,
        priority: RequestPriority,
        name: str,
        action: Callable[[], Awaitable[Any]],
    ) -> Any:
        if not self._started or not self.is_ready:
            raise ServiceUnavailableError("thermometer is not connected")
        try:
            return await self._scheduler.submit(priority, name, action)
        except RuntimeError as exc:
            if str(exc) == "thermometer is not connected":
                raise ServiceUnavailableError(str(exc)) from exc
            raise

    def _fail_queued_requests(self, error: Exception) -> None:
        self._scheduler.fail_pending(error)

    async def _synchronize_history(self, operation: TrackedOperation) -> HistorySync:
        retrieval = await self._history_synchronizer.synchronize(operation)
        history = replace(
            retrieval.history,
            persistence_configured=self.database.persistence_configured,
        )
        deadline = retrieval.deadline
        failures = list(retrieval.failures)
        started = deadline - self.settings.history_sync_budget_seconds

        batch = self._build_history_batch(history)
        upsert_future = self._persistence.enqueue("upsert_history", batch)
        reconcile_future = self._persistence.enqueue(
            "reconcile_provisional_intervals", batch
        )
        remaining_budget = deadline - self._monotonic()
        persisted = False
        if remaining_budget > 0:
            try:
                upsert, reconcile = await asyncio.wait_for(
                    asyncio.gather(
                        asyncio.shield(upsert_future),
                        asyncio.shield(reconcile_future),
                    ),
                    timeout=remaining_budget,
                )
                persisted = upsert.persisted and reconcile.persisted
            except asyncio.TimeoutError:
                failures.append("history persistence exceeded its time budget")
        else:
            failures.append("history persistence exceeded its time budget")

        elapsed = self._monotonic() - started
        if failures:
            history = replace(
                history,
                complete=False,
                elapsed_seconds=elapsed,
                failure_reason="; ".join(dict.fromkeys(failures)),
                persisted=persisted,
            )
        else:
            history = replace(
                history, elapsed_seconds=elapsed, persisted=persisted
            )
        operation.persistence_succeeded = persisted
        await self._emit({"type": "history", "history": history})
        return history

    def _build_history_batch(self, history: HistorySync) -> HistoryBatch:
        identity = self.target
        if identity is None:
            raise ServiceUnavailableError("history has no associated device")
        by_sequence: dict[int, dict[int, TimedHistoryRecord]] = {}
        for record in history.records:
            by_sequence.setdefault(record.sequence, {})[record.sensor_id] = record

        samples: list[SampleRecord] = []
        for sequence, sensor_records in by_sequence.items():
            readings: list[SensorReading] = []
            sample_time: datetime | None = None
            for sensor_id in range(1, CONFIG.device.sensor_count + 1):
                record = sensor_records.get(sensor_id)
                if record is None:
                    readings.append(
                        SensorReading(sensor_id, None, "NOT_RETRIEVED", None)
                    )
                    continue
                sample_time = record.sampled_at
                readings.append(
                    SensorReading(
                        sensor_id,
                        record.temperature_c,
                        record.data_status.name,
                        None,
                    )
                )
            temperatures = [
                reading.temperature_c
                for reading in readings
                if reading.temperature_c is not None
            ]
            average = (
                sum(temperatures) / CONFIG.device.sensor_count
                if len(temperatures) == CONFIG.device.sensor_count
                else None
            )
            samples.append(
                SampleRecord(
                    identity,
                    sample_time or self._utc_now(),
                    history.meta.boot_id,
                    sequence,
                    tuple(readings),
                    average,
                    "HISTORY",
                )
            )
        samples.sort(key=lambda sample: sample.observed_at_utc)
        return HistoryBatch(
            identity,
            history.meta.boot_id,
            self._history_previous_boot_id,
            self._history_is_new_boot,
            tuple(samples),
            history.expected_counts,
            history.retrieved_counts,
            history.complete,
            history.elapsed_seconds,
            history.failure_reason,
        )

    def _start_history_sync(self, source: str) -> TrackedOperation:
        if self._history_task is not None and not self._history_task.done():
            assert self._history_operation_id is not None
            return self._operations[self._history_operation_id]
        operation = self._new_operation(f"history_sync:{source}")
        operation.state = OperationState.RUNNING
        operation.updated_at_utc = self._utc_now()
        self._history_operation_id = operation.operation_id
        self._history_task = asyncio.create_task(
            self._synchronize_history(operation), name="thermometer-history-sync"
        )
        self._track_background(self._history_task)

        def finished(task: asyncio.Task[HistorySync]) -> None:
            if task.cancelled():
                self._cancel_operation(operation.operation_id, "history sync cancelled")
            else:
                error = task.exception()
                if error is not None:
                    self._fail_operation(operation, error)
                else:
                    history = task.result()
                    self._succeed_operation(
                        operation,
                        {
                            "expected_counts": list(history.expected_counts),
                            "retrieved_counts": list(history.retrieved_counts),
                            "complete": history.complete,
                            "elapsed_seconds": history.elapsed_seconds,
                            "failure_reason": history.failure_reason,
                        },
                    )
            if self._history_task is task:
                self._history_task = None
                self._history_operation_id = None

        self._history_task.add_done_callback(finished)
        return operation

    async def _cancel_history(self, reason: str) -> None:
        task = self._history_task
        if task is None or task.done():
            return
        task.cancel()
        # Another shutdown/reconnect path may be waiting on the same task, and
        # a task can finish with its own error just before cancellation lands.
        # Teardown must consume either outcome instead of leaking it to the loop.
        await asyncio.gather(task, return_exceptions=True)
        if self._history_operation_id:
            self._cancel_operation(self._history_operation_id, reason)
        self._history_task = None
        self._history_operation_id = None

    async def _publish_current_snapshot(
        self, snapshot: CurrentSnapshot, observed_at: datetime
    ) -> PersistenceResult:
        identity = self.target
        readings = tuple(
            SensorReading(
                sensor.sensor_id,
                sensor.temperature_c,
                (
                    DataStatus.VALID.name
                    if sensor.temperature_c is not None
                    else DataStatus.DISCONNECTED.name
                ),
                sensor.display_enabled,
            )
            for sensor in snapshot.sensors
        )
        temperatures = [
            reading.temperature_c
            for reading in readings
            if reading.temperature_c is not None
        ]
        # The database average uses both valid readings from this sample,
        # regardless of whether either display is currently visible.
        average = (
            sum(temperatures) / CONFIG.device.sensor_count
            if len(temperatures) == CONFIG.device.sensor_count
            else None
        )
        sample = SampleRecord(
            identity,
            observed_at,
            snapshot.boot_id,
            snapshot.newest_sequence,
            readings,
            average,
            "LIVE",
        )
        self._last_current = CurrentDiagnostic(True, observed_at, snapshot)
        if observed_at != self._state.last_seen_utc:
            self._transition(
                last_seen_utc=observed_at,
                reason="current snapshot received",
            )
        persistence_future = self._persistence.enqueue(
            "publish_current_sample", sample
        )
        await self._emit({"type": "snapshot", "snapshot": snapshot})
        if persistence_future.done():
            return persistence_future.result()
        return PersistenceResult(
            self.database.persistence_configured,
            False,
            "current sample queued for persistence",
        )

    async def _publish_missing_interval(
        self, observed_at: datetime, reason: str
    ) -> PersistenceResult:
        # Never reuse old values for a missed one-second slot.
        sample = SampleRecord(
            self.target,
            observed_at,
            None,
            None,
            tuple(
                SensorReading(sensor_id, None, "MISSING", None)
                for sensor_id in range(1, CONFIG.device.sensor_count + 1)
            ),
            None,
            "PROVISIONAL",
            provisional=True,
            failure_reason=reason,
        )
        self._last_current = CurrentDiagnostic(
            False, self._last_current.received_at_utc, None, reason
        )
        persistence_future = self._persistence.enqueue(
            "publish_missing_interval", sample
        )
        if persistence_future.done():
            return persistence_future.result()
        return PersistenceResult(
            self.database.persistence_configured,
            False,
            "missing interval queued for persistence",
        )

    async def _publish_connection_state(self) -> PersistenceResult:
        # Connection/last-seen state is observable separately from temperature
        # rows. The immutable snapshot is queued so neither a database write nor
        # an event handler can delay later BLE transitions.
        self._state_publish_queue.put_nowait(self._state)
        return PersistenceResult(
            self.database.persistence_configured,
            False,
            "connection state queued for publication",
        )

    async def _state_publisher(self) -> None:
        """Publish immutable revisions sequentially outside the BLE manager."""

        while True:
            state = await self._state_publish_queue.get()
            try:
                await self._persistence.submit(
                    "publish_connection_state",
                    ConnectionStateRecord(
                        self._device_identity(state.target),
                        state.changed_at_utc,
                        state.phase.value,
                        state.connected,
                        state.last_seen_utc,
                        state.last_error,
                        state.ready,
                        state.revision,
                        state.reason,
                    ),
                )
                await self._emit(
                    {
                        "type": "service_status",
                        "status": self._status_from_state(state),
                    }
                )
            finally:
                self._state_publish_queue.task_done()

    async def _database_call(self, method_name: str, argument: Any) -> PersistenceResult:
        # Persistence failures affect only this write/cycle.
        try:
            method = getattr(self.database, method_name)
            result = await method(argument)
            self._database_errors.pop(method_name, None)
            self._last_database_error = (
                next(reversed(self._database_errors.values()))
                if self._database_errors
                else None
            )
            return result
        except Exception as exc:
            message = describe_ble_error(exc)
            self._database_errors[method_name] = message
            self._last_database_error = message
            LOGGER.exception("database adapter %s failed", method_name)
            await self._emit(
                {
                    "type": "database_error",
                    "operation": method_name,
                    "message": message,
                }
            )
            return PersistenceResult(
                self.database.persistence_configured, False, message
            )

    async def _read_last_persisted_boot(
        self, target: DiscoveredThermometer
    ) -> int | None:
        """Load restart continuity when the selected adapter supports it."""

        method = getattr(self.database, "get_last_boot_id", None)
        if method is None:
            return None
        try:
            boot_id = await method(self._device_identity(target))
            if boot_id is None:
                return None
            if not isinstance(boot_id, int) or not 0 <= boot_id <= 0xFFFFFFFF:
                raise ValueError("database returned an invalid boot ID")
            return boot_id
        except Exception as exc:
            message = describe_ble_error(exc)
            self._database_errors["get_last_boot_id"] = message
            self._last_database_error = message
            LOGGER.exception("database adapter get_last_boot_id failed")
            return None

    async def _scan_for_devices(
        self, timeout: float
    ) -> list[DiscoveredThermometer]:
        async with self._scan_lock:
            if self._scan_task is None or self._scan_task.done():
                self._scan_task = asyncio.create_task(
                    self._perform_scan(timeout), name="thermometer-shared-scan"
                )
            scan_task = self._scan_task
        try:
            return await asyncio.shield(scan_task)
        finally:
            async with self._scan_lock:
                if self._scan_task is scan_task and scan_task.done():
                    self._scan_task = None

    async def _perform_scan(self, timeout: float) -> list[DiscoveredThermometer]:
        # Bleak normally applies its own scan timeout. This outer deadline also
        # covers a Windows watcher that stalls while stopping, so DISCOVERING
        # can never accidentally become a terminal state.
        scan_deadline = timeout + self.settings.auto_discovery_interval_seconds
        try:
            discovered = await asyncio.wait_for(
                self._discover(timeout=timeout), timeout=scan_deadline
            )
        except asyncio.TimeoutError as exc:
            raise ServiceUnavailableError(
                f"BLE discovery did not finish within {scan_deadline:g} seconds"
            ) from exc
        devices = [
            self._with_best_known_name(device)
            for device in discovered
        ]
        for device in devices:
            self._known_devices[device.address.lower()] = device
        await self._emit({"type": "devices", "devices": devices})
        return devices

    async def _next_discovery_observation(
        self,
    ) -> list[DiscoveredThermometer]:
        """Consume a queued manual observation or actively scan."""

        if self._pending_discovery is not None:
            devices = list(self._pending_discovery)
            self._pending_discovery = None
            return devices
        return await self._scan_for_devices(
            self.settings.startup_scan_timeout_seconds
        )

    async def _find_reconnect_target(
        self,
        selected_target: DiscoveredThermometer,
        selected_generation: int,
    ) -> DiscoveredThermometer | None:
        """Rediscover one selected ESP32 before reopening its GATT link."""

        devices = await self._scan_for_devices(
            self.settings.startup_scan_timeout_seconds
        )
        if (
            not self._desired_connected
            or selected_generation != self._target_generation
        ):
            return None

        selected_address = selected_target.address.lower()
        refreshed = next(
            (
                device
                for device in devices
                if device.address.lower() == selected_address
            ),
            None,
        )
        if refreshed is None:
            raise ServiceUnavailableError(
                f"selected thermometer {selected_target.address} is not advertising"
            )

        self._transition(
            ConnectionPhase.RECONNECTING,
            target=refreshed,
            connected=False,
            ready=False,
            reason="selected thermometer rediscovered",
        )
        await self._publish_connection_state()
        return refreshed

    @staticmethod
    def _has_useful_device_name(name: Any, address: str) -> bool:
        if not isinstance(name, str) or not name.strip():
            return False
        normalized_name = name.strip().casefold()
        return normalized_name not in {"unknown", "(unknown)"} and (
            normalized_name != address.strip().casefold()
        )

    def _with_best_known_name(
        self, device: DiscoveredThermometer
    ) -> DiscoveredThermometer:
        """Preserve a real name when a Windows scan omits the scan response."""

        if self._has_useful_device_name(device.name, device.address):
            return device

        known = self._known_devices.get(device.address.lower())
        if known is not None and self._has_useful_device_name(
            known.name, device.address
        ):
            return replace(device, name=known.name)

        stored = self.credentials.lookup(device.address)
        stored_name = getattr(stored, "device_name", None)
        if self._has_useful_device_name(stored_name, device.address):
            return replace(device, name=stored_name.strip())
        return replace(device, name=display_name(None, device.address))

    def _resolve_target(
        self, target: str | DiscoveredThermometer | Any
    ) -> DiscoveredThermometer:
        if isinstance(target, DiscoveredThermometer):
            return target
        address = getattr(target, "address", target)
        if not isinstance(address, str) or not address.strip():
            raise ValueError("a non-empty BLE address is required")
        known = self._known_devices.get(address.lower())
        if known is not None:
            return known
        name = display_name(getattr(target, "name", None), address)
        return DiscoveredThermometer(name, address, target, None)

    @staticmethod
    def _device_identity(
        target: DiscoveredThermometer | None,
    ) -> DeviceIdentity | None:
        if target is None:
            return None
        return DeviceIdentity(target.address, target.name)

    def _required_client(self) -> ThermometerBleClient:
        if self._client is None or not self._client.is_connected:
            raise ServiceUnavailableError("thermometer is not connected")
        return self._client

    def _post_manager_event(
        self,
        kind: LifecycleEventType,
        reason: str,
        value: Any = None,
        *,
        generation: int | None = None,
    ) -> None:
        if not self._started and kind is not LifecycleEventType.STOP:
            return
        self._manager_events.put_nowait(
            LifecycleEvent(
                kind,
                self._target_generation if generation is None else generation,
                reason,
                value,
            )
        )

    def _notify_connection_manager(self) -> None:
        self._post_manager_event(
            LifecycleEventType.INTENT_CHANGED, "connection intent changed"
        )

    async def _wait_for_manager_wakeup(self, timeout: float | None) -> None:
        try:
            event = (
                await self._manager_events.get()
                if timeout is None
                else await asyncio.wait_for(
                    self._manager_events.get(), timeout=timeout
                )
            )
        except asyncio.TimeoutError:
            return

        try:
            if (
                event.kind is LifecycleEventType.DISCOVERY_RESULT
                and event.generation == self._target_generation
                and self._target is None
            ):
                self._pending_discovery = tuple(event.value or ())
            elif event.kind is LifecycleEventType.LINK_LOST:
                if (
                    event.generation == self._target_generation
                    and event.value is self._client
                ):
                    await self._connection_lost(event.reason, close_client=True)
        finally:
            self._manager_events.task_done()

    def _update_cached_display(self, result: DisplayResult) -> None:
        diagnostic = self._last_current
        if diagnostic.snapshot is None:
            return
        sensors = tuple(
            replace(
                sensor,
                visible_state=result.visible_state,
                display_enabled=result.display_enabled,
            )
            if sensor.sensor_id == result.sensor_id
            else sensor
            for sensor in diagnostic.snapshot.sensors
        )
        snapshot = replace(diagnostic.snapshot, sensors=sensors)
        self._last_current = replace(diagnostic, snapshot=snapshot)

    def _new_operation(self, kind: str) -> TrackedOperation:
        self._prune_operations()
        now = self._utc_now()
        operation = TrackedOperation(
            str(uuid.uuid4()),
            kind,
            OperationState.QUEUED,
            now,
            now,
            persistence_configured=self.database.persistence_configured,
        )
        self._operations[operation.operation_id] = operation
        self._operation_events[operation.operation_id] = asyncio.Event()
        return operation

    def _launch_operation(
        self, kind: str, coroutine: Coroutine[Any, Any, dict[str, Any]]
    ) -> TrackedOperation:
        operation = self._new_operation(kind)

        async def run() -> None:
            operation.state = OperationState.RUNNING
            operation.updated_at_utc = self._utc_now()
            try:
                result = await coroutine
            except asyncio.CancelledError:
                self._cancel_operation(operation.operation_id, "operation cancelled")
                raise
            except Exception as exc:
                self._fail_operation(operation, exc)
            else:
                self._succeed_operation(operation, result)

        self._track_background(asyncio.create_task(run(), name=f"operation-{kind}"))
        return operation

    def _track_background(self, task: asyncio.Task[Any]) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _succeed_operation(
        self, operation: TrackedOperation, result: dict[str, Any]
    ) -> None:
        operation.state = OperationState.SUCCEEDED
        operation.progress = 1.0
        operation.result = result
        operation.updated_at_utc = self._utc_now()
        completion = self._operation_events.get(operation.operation_id)
        if completion is not None:
            completion.set()

    def _fail_operation(self, operation: TrackedOperation, error: BaseException) -> None:
        operation.state = OperationState.FAILED
        operation.error = {
            "type": type(error).__name__,
            "message": describe_ble_error(error),
        }
        operation.updated_at_utc = self._utc_now()
        completion = self._operation_events.get(operation.operation_id)
        if completion is not None:
            completion.set()

    def _cancel_operation(self, operation_id: str, reason: str) -> None:
        operation = self._operations.get(operation_id)
        if operation is None or operation.state not in {
            OperationState.QUEUED,
            OperationState.RUNNING,
        }:
            return
        operation.state = OperationState.CANCELLED
        operation.error = {"type": "CancelledError", "message": reason}
        operation.updated_at_utc = self._utc_now()
        completion = self._operation_events.get(operation_id)
        if completion is not None:
            completion.set()

    def _complete_pending_connect(self) -> None:
        if not self._pending_connect_operation_id:
            return
        operation = self._operations.get(self._pending_connect_operation_id)
        if operation is not None:
            self._succeed_operation(
                operation,
                {"address": self._target.address if self._target else None},
            )
        self._pending_connect_operation_id = None

    def _fail_pending_connect(self, message: str) -> None:
        if not self._pending_connect_operation_id:
            return
        operation = self._operations.get(self._pending_connect_operation_id)
        if operation is not None:
            self._fail_operation(operation, RuntimeError(message))
        self._pending_connect_operation_id = None

    def _prune_operations(self) -> None:
        cutoff = self._utc_now() - timedelta(
            seconds=self.settings.completed_operation_retention_seconds
        )
        expired = [
            operation_id
            for operation_id, operation in self._operations.items()
            if operation.state
            not in {OperationState.QUEUED, OperationState.RUNNING}
            and operation.updated_at_utc < cutoff
        ]
        for operation_id in expired:
            del self._operations[operation_id]
            self._operation_events.pop(operation_id, None)

    async def _emit(self, event: ServiceEvent) -> None:
        if self._event_handler is None:
            return
        try:
            result = self._event_handler(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            LOGGER.exception("service event handler failed")
