import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import time
import unittest
from types import SimpleNamespace

from pc_client.ble_service import (
    AuthenticationRequiredError,
    ConnectionPhase,
    CredentialState,
    OperationState,
    ThermometerBleService,
)
from pc_client.database_adapter import PersistenceResult
from pc_client.protocol import (
    CONFIG,
    CurrentSnapshot,
    DataStatus,
    DisplayResult,
    HistoryChunk,
    HistoryMeta,
    HistoryRecordValue,
    SensorSnapshot,
    ProtocolError,
    Status,
    VisibleState,
)
from pc_client.thermometer_client import DiscoveredThermometer


FAST_SETTINGS = replace(
    CONFIG.service,
    startup_scan_timeout_seconds=0.01,
    auto_discovery_interval_seconds=0.02,
    poll_interval_seconds=0.03,
    poll_tolerance_seconds=0.005,
    history_sync_budget_seconds=0.5,
    display_command_timeout_seconds=0.2,
    completed_operation_retention_seconds=1.0,
)


def snapshot(sequence: int = 10) -> CurrentSnapshot:
    return CurrentSnapshot(
        77,
        sequence,
        (
            SensorSnapshot(1, 20.0, VisibleState.OFF, False),
            SensorSnapshot(2, 22.0, VisibleState.ON, True),
        ),
        21.0,
    )


class FakeDatabase:
    persistence_configured = True

    def __init__(self) -> None:
        self.current = []
        self.missing = []
        self.history = []
        self.connections = []
        self.displays = []

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def publish_current_sample(self, value):
        self.current.append(value)
        return PersistenceResult(True, True)

    async def publish_missing_interval(self, value):
        self.missing.append(value)
        return PersistenceResult(True, True)

    async def upsert_history(self, value):
        self.history.append(value)
        return PersistenceResult(True, True)

    async def reconcile_provisional_intervals(self, value):
        return PersistenceResult(True, True)

    async def publish_connection_state(self, value):
        self.connections.append(value)
        return PersistenceResult(True, True)

    async def publish_display_result(self, value):
        self.displays.append(value)
        return PersistenceResult(True, True)


class FakeClient:
    def __init__(self, _target) -> None:
        self.is_connected = False
        self.calls = []
        self.sequence = 10
        self.first_chunk_started = asyncio.Event()
        self.release_first_chunk = asyncio.Event()
        self.pause_first_chunk = False
        self.chunk_failures_remaining = 0
        self.slow_chunk_seconds = 0.0
        self.disconnected_callback = None
        self.authentication_error = None
        self.forget_error = None

    def set_disconnected_callback(self, callback) -> None:
        self.disconnected_callback = callback

    async def connect(self, *_args, **_kwargs) -> None:
        self.calls.append("connect")
        self.is_connected = True

    async def close(self) -> None:
        self.calls.append("close")
        self.is_connected = False

    async def pair(self, passkey: str) -> None:
        assert len(passkey) == 6
        self.calls.append("pair")

    async def authenticate(self, passkey: str) -> None:
        assert len(passkey) == 6
        self.calls.append("authenticate")
        if self.authentication_error is not None:
            raise self.authentication_error

    async def request_bond_reset(self) -> None:
        self.calls.append("reset_bond")

    async def forget_pairing(self) -> None:
        self.calls.append("forget")
        if self.forget_error is not None:
            raise self.forget_error

    async def get_current(self) -> CurrentSnapshot:
        self.calls.append("current")
        return snapshot(self.sequence)

    async def set_display(self, sensor_id: int, enabled: bool) -> DisplayResult:
        self.calls.append(f"display:{sensor_id}:{enabled}")
        return DisplayResult(
            sensor_id, VisibleState.ON if enabled else VisibleState.OFF, enabled
        )

    async def get_history_meta(self) -> HistoryMeta:
        self.calls.append("meta")
        return HistoryMeta(77, 10, (4, 4), (7, 7))

    async def get_history_chunk(
        self, sensor_id: int, start_sequence: int, count: int
    ) -> HistoryChunk:
        self.calls.append(f"chunk:{sensor_id}:{start_sequence}:{count}")
        if self.chunk_failures_remaining:
            self.chunk_failures_remaining -= 1
            from pc_client.protocol import ProtocolError, Status

            raise ProtocolError("ring advanced", Status.NOT_AVAILABLE)
        if self.slow_chunk_seconds:
            await asyncio.sleep(self.slow_chunk_seconds)
        if self.pause_first_chunk and not self.first_chunk_started.is_set():
            self.first_chunk_started.set()
            await self.release_first_chunk.wait()
        return HistoryChunk(
            sensor_id,
            start_sequence,
            tuple(
                HistoryRecordValue(
                    (start_sequence + offset) & 0xFFFFFFFF,
                    20.0 + sensor_id,
                    DataStatus.VALID,
                )
                for offset in range(count)
            ),
        )

    def records_per_chunk(self) -> int:
        return 2


class FakeCredentials:
    def __init__(self) -> None:
        self.records = {}

    def enroll(
        self,
        address: str,
        passkey: str = "123456",
        device_name: str = "Thermometer-Test-01",
    ) -> None:
        self.records[address.lower()] = SimpleNamespace(
            pairing_passkey=passkey, device_name=device_name
        )

    def lookup(self, address: str):
        return self.records.get(address.lower())

    def save_verified(
        self, address: str, device_name: str, passkey: str, **_kwargs
    ):
        self.enroll(address, passkey, device_name)
        return self.records[address.lower()]

    def delete(self, address: str) -> bool:
        return self.records.pop(address.lower(), None) is not None


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleepers = []

    def monotonic(self) -> float:
        return self.now

    def utc_now(self) -> datetime:
        from datetime import timedelta

        return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=self.now)

    async def sleep(self, delay: float) -> None:
        if delay <= 0:
            await asyncio.sleep(0)
            return
        future = asyncio.get_running_loop().create_future()
        self.sleepers.append((self.now + delay, future))
        await future

    def advance(self, seconds: float) -> None:
        self.now += seconds
        ready = [item for item in self.sleepers if item[0] <= self.now]
        self.sleepers = [item for item in self.sleepers if item[0] > self.now]
        for _deadline, future in ready:
            if not future.done():
                future.set_result(None)


async def wait_until(predicate, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise asyncio.TimeoutError
        await asyncio.sleep(0.005)


class BleServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.device = DiscoveredThermometer(
            "Thermometer-Test-01", "AA:BB:CC:DD:EE:FF", object(), -40
        )
        self.database = FakeDatabase()
        self.credentials = FakeCredentials()
        self.credentials.enroll(self.device.address)
        self.clients = []

        def client_factory(target):
            client = FakeClient(target)
            self.clients.append(client)
            return client

        self.client_factory = client_factory
        self.services = []

    async def asyncTearDown(self) -> None:
        await asyncio.gather(
            *(service.stop() for service in self.services), return_exceptions=True
        )

    def make_service(self, discovered, *, auto=True) -> ThermometerBleService:
        async def discover(*, timeout):
            return list(discovered)

        service = ThermometerBleService(
            database=self.database,
            client_factory=self.client_factory,
            discover=discover,
            auto_discover_on_start=auto,
            settings=FAST_SETTINGS,
            credential_registry=self.credentials,
        )
        self.services.append(service)
        return service

    async def test_startup_auto_connects_only_device_and_publishes_current_first(self):
        service = self.make_service([self.device])
        await service.start()
        await wait_until(lambda: service.get_status().connected)
        await wait_until(lambda: bool(self.database.history))

        self.assertEqual(service.get_status().phase, ConnectionPhase.CONNECTED)
        self.assertTrue(service.get_current().available)
        self.assertTrue(self.database.current)
        self.assertEqual(self.database.current[0].average_temperature_c, 21.0)
        self.assertLess(self.database.current[0].observed_at_utc, datetime.now(timezone.utc))

    async def test_startup_discovers_device_that_is_powered_on_later(self):
        visible_devices = []
        scan_count = 0

        async def discover(*, timeout):
            nonlocal scan_count
            scan_count += 1
            return list(visible_devices)

        service = ThermometerBleService(
            database=self.database,
            client_factory=self.client_factory,
            discover=discover,
            settings=FAST_SETTINGS,
            credential_registry=self.credentials,
        )
        self.services.append(service)
        await service.start()
        await wait_until(lambda: scan_count >= 2)

        visible_devices.append(self.device)
        await wait_until(lambda: service.is_ready)

        self.assertGreaterEqual(scan_count, 3)
        self.assertEqual(service.get_status().phase, ConnectionPhase.CONNECTED)

    async def test_startup_recovers_from_a_discovery_failure_without_api_input(self):
        scan_count = 0

        async def discover(*, timeout):
            nonlocal scan_count
            scan_count += 1
            if scan_count == 1:
                raise RuntimeError("Bluetooth watcher failed")
            return [self.device]

        service = ThermometerBleService(
            database=self.database,
            client_factory=self.client_factory,
            discover=discover,
            settings=FAST_SETTINGS,
            credential_registry=self.credentials,
        )
        self.services.append(service)
        await service.start()
        await wait_until(lambda: service.is_ready)

        self.assertGreaterEqual(scan_count, 2)
        self.assertEqual(service.get_status().phase, ConnectionPhase.CONNECTED)

    async def test_multiple_devices_require_explicit_selection(self):
        second = DiscoveredThermometer(
            "Thermometer-Test-02", "11:22:33:44:55:66", object(), -50
        )
        service = self.make_service([self.device, second])
        await service.start()
        await wait_until(
            lambda: service.get_status().phase is ConnectionPhase.SELECTION_REQUIRED
        )

        self.assertFalse(service.is_connected)
        self.assertIsNone(service.target)

    async def test_explicit_disconnect_suppresses_reconnection_but_keeps_target(self):
        service = self.make_service([self.device])
        await service.start()
        await wait_until(lambda: service.is_connected)

        await service.disconnect()
        await asyncio.sleep(FAST_SETTINGS.auto_discovery_interval_seconds * 2)

        status = service.get_status()
        self.assertFalse(status.desired_connected)
        self.assertFalse(status.connected)
        self.assertEqual(status.target.address, self.device.address)
        self.assertEqual(len(self.clients), 1)

    async def test_history_is_metadata_first_recent_first_and_round_robin(self):
        service = self.make_service([], auto=False)
        await service.start()
        operation = await service.connect(self.device)
        operation = await service.wait_for_operation(operation.operation_id, 1)
        self.assertEqual(operation.state, OperationState.SUCCEEDED)
        await wait_until(lambda: bool(self.database.history))

        calls = self.clients[0].calls
        meta_index = calls.index("meta")
        chunk_calls = [call for call in calls if call.startswith("chunk:")]
        self.assertLess(meta_index, calls.index(chunk_calls[0]))
        self.assertEqual(
            chunk_calls[:4],
            ["chunk:1:9:2", "chunk:2:9:2", "chunk:1:7:2", "chunk:2:7:2"],
        )
        batch = self.database.history[0]
        self.assertTrue(batch.complete)
        self.assertEqual(batch.expected_counts, (4, 4))
        self.assertEqual(batch.retrieved_counts, (4, 4))

    async def test_display_preempts_history_between_chunks(self):
        service = self.make_service([], auto=False)
        await service.start()
        connect_operation = await service.connect(self.device)
        await service.wait_for_operation(connect_operation.operation_id, 1)
        client = self.clients[0]
        await wait_until(
            lambda: bool(self.database.history) and service._history_task is None
        )

        client.pause_first_chunk = True
        history_operation = await service.request_history_sync()
        await client.first_chunk_started.wait()
        duplicate = await service.request_history_sync()
        display_task = asyncio.create_task(service.set_display(1, True))
        client.release_first_chunk.set()
        display = await display_task
        await service.wait_for_operation(history_operation.operation_id, 1)

        calls = client.calls
        first_chunk = max(
            index for index, value in enumerate(calls) if value == "chunk:1:9:2"
        )
        display_index = calls.index("display:1:True", first_chunk)
        next_chunk = calls.index("chunk:2:9:2", first_chunk + 1)
        self.assertLess(display_index, next_chunk)
        self.assertTrue(display.result.display_enabled)
        self.assertEqual(duplicate.operation_id, history_operation.operation_id)

    async def test_history_retries_a_chunk_twice_before_succeeding(self):
        service = self.make_service([], auto=False)
        await service.start()
        connect_operation = await service.connect(self.device)
        await service.wait_for_operation(connect_operation.operation_id, 1)
        await wait_until(
            lambda: bool(self.database.history) and service._history_task is None
        )
        client = self.clients[0]
        client.calls.clear()
        client.chunk_failures_remaining = 2

        history_operation = await service.request_history_sync()
        completed = await service.wait_for_operation(history_operation.operation_id, 1)

        self.assertEqual(
            completed.state,
            OperationState.SUCCEEDED,
            getattr(completed, "error", None),
        )
        self.assertEqual(client.calls.count("chunk:1:9:2"), 3)
        self.assertTrue(completed.result["complete"])

    async def test_history_budget_persists_and_reports_partial_results(self):
        service = self.make_service([], auto=False)
        await service.start()
        connect_operation = await service.connect(self.device)
        await service.wait_for_operation(connect_operation.operation_id, 1)
        await wait_until(
            lambda: bool(self.database.history) and service._history_task is None
        )
        self.database.history.clear()
        # Let metadata complete, then deterministically exhaust the budget on
        # the first chunk. A 30 ms budget for the whole initial connection was
        # scheduler-dependent and could expire before metadata existed, where
        # no meaningful partial batch can be produced.
        service.settings = replace(
            FAST_SETTINGS,
            history_sync_budget_seconds=0.1,
            poll_interval_seconds=1.0,
            poll_tolerance_seconds=0.1,
        )
        client = self.clients[0]
        client.slow_chunk_seconds = 0.5

        history_operation = await service.request_history_sync()
        completed = await service.wait_for_operation(history_operation.operation_id, 1)

        self.assertEqual(
            completed.state,
            OperationState.SUCCEEDED,
            getattr(completed, "error", None),
        )
        self.assertFalse(completed.result["complete"])
        self.assertIn("time budget", completed.result["failure_reason"])
        self.assertEqual(len(self.database.history), 1)
        self.assertFalse(self.database.history[0].complete)

    async def test_unexpected_disconnect_reconnects_to_process_target(self):
        service = self.make_service([self.device])
        await service.start()
        await wait_until(lambda: service.is_connected)
        self.clients[0].is_connected = False

        await wait_until(lambda: len(self.clients) >= 2 and service.is_connected)

        self.assertTrue(service.get_status().desired_connected)
        self.assertEqual(service.target.address, self.device.address)

    async def test_failed_gatt_open_returns_to_reconnect_probe_and_recovers(self):
        class FirstConnectFails(FakeClient):
            async def connect(self, *_args, **_kwargs) -> None:
                self.calls.append("connect")
                raise RuntimeError("adapter still releasing old session")

        def client_factory(target):
            client = (
                FirstConnectFails(target) if not self.clients else FakeClient(target)
            )
            self.clients.append(client)
            return client

        self.client_factory = client_factory
        service = self.make_service([self.device])
        await service.start()
        await wait_until(lambda: len(self.clients) == 2 and service.is_ready)

        status = service.get_status()
        self.assertEqual(status.phase, ConnectionPhase.CONNECTED)
        self.assertEqual(status.retry_count, 0)

    async def test_reconnect_waits_for_restarted_device_and_refreshes_target(self):
        visible_devices = [self.device]
        service = self.make_service(visible_devices)
        await service.start()
        await wait_until(lambda: service.is_ready)

        visible_devices.clear()
        first_client = self.clients[0]
        first_client.is_connected = False
        first_client.disconnected_callback(first_client)
        await wait_until(
            lambda: service.get_status().phase is ConnectionPhase.RECONNECTING
        )
        await asyncio.sleep(FAST_SETTINGS.auto_discovery_interval_seconds * 2)

        # No second GATT client is created while the selected address is not
        # advertising. This avoids repeatedly opening a stale Windows object.
        self.assertEqual(len(self.clients), 1)
        refreshed_transport = object()
        visible_devices.append(replace(self.device, device=refreshed_transport))
        await wait_until(lambda: len(self.clients) == 2 and service.is_ready)

        self.assertIs(service._target.device, refreshed_transport)
        self.assertEqual(service.get_status().phase, ConnectionPhase.CONNECTED)

    async def test_late_disconnect_from_replaced_client_is_ignored(self):
        service = self.make_service([self.device])
        await service.start()
        await wait_until(lambda: service.is_ready)

        first_client = self.clients[0]
        first_client.is_connected = False
        first_client.disconnected_callback(first_client)
        await wait_until(lambda: len(self.clients) == 2 and service.is_ready)

        # Windows may deliver a delayed callback from the discarded transport.
        # It must not tear down the newer authenticated session.
        first_client.disconnected_callback(first_client)
        await asyncio.sleep(FAST_SETTINGS.auto_discovery_interval_seconds * 2)

        self.assertEqual(len(self.clients), 2)
        self.assertTrue(service.is_ready)
        self.assertEqual(service.get_status().phase, ConnectionPhase.CONNECTED)

    async def test_reconnect_continues_when_old_client_cleanup_stalls(self):
        never_finishes = asyncio.Event()

        class SlowCleanupClient(FakeClient):
            async def close(self) -> None:
                self.calls.append("close")
                self.is_connected = False
                await never_finishes.wait()

        def client_factory(target):
            client = (
                SlowCleanupClient(target) if not self.clients else FakeClient(target)
            )
            self.clients.append(client)
            return client

        self.client_factory = client_factory
        service = self.make_service([self.device])
        await service.start()
        await wait_until(lambda: service.is_ready)

        first_client = self.clients[0]
        first_client.is_connected = False
        with self.assertLogs("pc_client.ble_service", level="WARNING"):
            first_client.disconnected_callback(first_client)
            await wait_until(lambda: len(self.clients) == 2 and service.is_ready)

        self.assertEqual(service.get_status().phase, ConnectionPhase.CONNECTED)

    async def test_scan_recovers_registered_name_when_windows_reports_unknown(self):
        unknown_device = replace(self.device, name="(Unknown)")
        service = self.make_service([unknown_device], auto=False)
        await service.start()

        devices = await service.scan()

        self.assertEqual(devices[0].name, self.device.name)

    async def test_disconnected_poll_cycles_publish_distinct_provisional_slots(self):
        service = self.make_service([], auto=False)
        await service.start()
        await wait_until(lambda: len(self.database.missing) >= 3)

        self.assertGreaterEqual(len(self.database.missing), 3)
        samples = self.database.missing[:3]
        self.assertTrue(all(sample.provisional for sample in samples))
        self.assertTrue(all(sample.average_temperature_c is None for sample in samples))
        spacings = [
            (right.observed_at_utc - left.observed_at_utc).total_seconds()
            for left, right in zip(samples, samples[1:])
        ]
        self.assertEqual(spacings, [FAST_SETTINGS.poll_interval_seconds] * 2)

    async def test_database_failure_does_not_terminate_connection_worker(self):
        original = self.database.publish_current_sample
        failures = 1

        async def fail_once(value):
            nonlocal failures
            if failures:
                failures -= 1
                raise RuntimeError("database offline")
            return await original(value)

        self.database.publish_current_sample = fail_once
        service = self.make_service([self.device])
        with self.assertLogs("pc_client.ble_service", level="ERROR"):
            await service.start()
            await wait_until(lambda: service.is_connected)
            await wait_until(lambda: bool(self.database.current))

        self.assertTrue(service.is_connected)
        self.assertTrue(service.get_current().available)

    async def test_monotonic_scheduler_produces_300_one_second_slots(self):
        clock = ManualClock()

        async def discover(*, timeout):
            return []

        service = ThermometerBleService(
            database=self.database,
            client_factory=self.client_factory,
            discover=discover,
            auto_discover_on_start=False,
            settings=replace(
                FAST_SETTINGS,
                poll_interval_seconds=1.0,
                poll_tolerance_seconds=0.1,
            ),
            monotonic=clock.monotonic,
            utc_now=clock.utc_now,
            sleep=clock.sleep,
            credential_registry=self.credentials,
        )
        self.services.append(service)
        await service.start()
        await asyncio.sleep(0)

        for expected_count in range(1, 301):
            while not clock.sleepers:
                await asyncio.sleep(0)
            clock.advance(1.0)
            while len(self.database.missing) < expected_count:
                await asyncio.sleep(0)

        self.assertEqual(len(self.database.missing), 300)
        self.assertEqual(
            (
                self.database.missing[-1].observed_at_utc
                - self.database.missing[0].observed_at_utc
            ).total_seconds(),
            299.0,
        )

    async def test_unknown_single_device_waits_for_pin_then_enrolls(self):
        self.credentials.records.clear()
        service = self.make_service([self.device])
        await service.start()
        await wait_until(
            lambda: service.get_status().phase
            is ConnectionPhase.AUTHENTICATION_REQUIRED
        )

        status = service.get_status()
        self.assertFalse(status.connected)
        self.assertEqual(status.credential_state, CredentialState.MISSING)
        with self.assertRaises(AuthenticationRequiredError):
            await service.connect(self.device)

        operation = await service.connect(self.device, "012345")
        completed = await service.wait_for_operation(operation.operation_id, 1)
        self.assertEqual(completed.state, OperationState.SUCCEEDED)
        self.assertTrue(service.get_status().ready)
        self.assertEqual(
            self.credentials.lookup(self.device.address).pairing_passkey,
            "012345",
        )

    async def test_connected_state_does_not_wait_for_persistence(self):
        publish_started = asyncio.Event()
        release_publish = asyncio.Event()
        original = self.database.publish_connection_state

        async def block_connected(value):
            if value.phase == ConnectionPhase.CONNECTED.value:
                publish_started.set()
                await release_publish.wait()
            return await original(value)

        self.database.publish_connection_state = block_connected
        service = self.make_service([self.device])
        await service.start()
        await publish_started.wait()

        status = service.get_status()
        self.assertEqual(status.phase, ConnectionPhase.CONNECTED)
        self.assertTrue(status.connected)
        self.assertTrue(status.ready)
        release_publish.set()

    async def test_rejected_application_credential_stops_automatic_retry(self):
        def rejecting_factory(target):
            client = FakeClient(target)
            client.authentication_error = ProtocolError(
                "proof rejected", Status.AUTHENTICATION_FAILED
            )
            self.clients.append(client)
            return client

        self.client_factory = rejecting_factory
        service = self.make_service([], auto=False)
        await service.start()
        operation = await service.connect(self.device)
        completed = await service.wait_for_operation(operation.operation_id, 1)
        await wait_until(
            lambda: service.get_status().phase
            is ConnectionPhase.AUTHENTICATION_REQUIRED
        )

        self.assertEqual(completed.state, OperationState.FAILED)
        self.assertEqual(
            service.get_status().credential_state, CredentialState.REJECTED
        )
        # An unrelated discovery result is a manager wake-up, but must not
        # retry a credential which requires an explicit user replacement.
        await service.scan()
        await asyncio.sleep(FAST_SETTINGS.auto_discovery_interval_seconds * 2)
        self.assertEqual(len(self.clients), 1)

    async def test_pairing_reset_is_authorized_and_ordered(self):
        service = self.make_service([], auto=False)
        await service.start()
        connect_operation = await service.connect(self.device)
        await service.wait_for_operation(connect_operation.operation_id, 1)

        reset_operation = await service.forget_pairing(self.device)
        completed = await service.wait_for_operation(reset_operation.operation_id, 1)

        self.assertEqual(completed.state, OperationState.SUCCEEDED)
        calls = self.clients[0].calls
        self.assertLess(calls.index("reset_bond"), calls.index("close"))
        self.assertLess(calls.index("close"), calls.index("forget"))
        self.assertIsNone(self.credentials.lookup(self.device.address))
        status = service.get_status()
        self.assertEqual(status.phase, ConnectionPhase.DISCONNECTED)
        self.assertFalse(status.desired_connected)

    async def test_pairing_reset_partial_failure_remains_observable(self):
        service = self.make_service([], auto=False)
        await service.start()
        connect_operation = await service.connect(self.device)
        await service.wait_for_operation(connect_operation.operation_id, 1)
        self.clients[0].forget_error = RuntimeError("Windows refused removal")

        reset_operation = await service.forget_pairing(self.device)
        completed = await service.wait_for_operation(reset_operation.operation_id, 1)

        self.assertEqual(completed.state, OperationState.FAILED)
        self.assertIsNotNone(self.credentials.lookup(self.device.address))
        status = service.get_status()
        self.assertEqual(status.phase, ConnectionPhase.DISCONNECTED)
        self.assertIn("Windows bond removal", status.last_error)

    async def test_manual_scan_joins_startup_discovery(self):
        scan_started = asyncio.Event()
        release_scan = asyncio.Event()
        call_count = 0

        async def discover(*, timeout):
            nonlocal call_count
            call_count += 1
            scan_started.set()
            await release_scan.wait()
            return []

        service = ThermometerBleService(
            database=self.database,
            client_factory=self.client_factory,
            discover=discover,
            settings=replace(
                FAST_SETTINGS,
                startup_scan_timeout_seconds=0.1,
                auto_discovery_interval_seconds=0.1,
            ),
            credential_registry=self.credentials,
        )
        self.services.append(service)
        await service.start()
        await scan_started.wait()
        manual_scan = asyncio.create_task(service.scan())
        await asyncio.sleep(0)
        release_scan.set()

        self.assertEqual(await manual_scan, [])
        self.assertEqual(call_count, 1)

    async def test_manual_selection_wins_over_in_flight_discovery(self):
        scan_started = asyncio.Event()
        release_scan = asyncio.Event()

        async def discover(*, timeout):
            scan_started.set()
            await release_scan.wait()
            return []

        service = ThermometerBleService(
            database=self.database,
            client_factory=self.client_factory,
            discover=discover,
            settings=FAST_SETTINGS,
            credential_registry=self.credentials,
        )
        self.services.append(service)
        await service.start()
        await scan_started.wait()
        operation = await service.connect(self.device)
        release_scan.set()
        completed = await service.wait_for_operation(operation.operation_id, 1)

        self.assertEqual(
            completed.state,
            OperationState.SUCCEEDED,
            getattr(completed, "error", None),
        )
        self.assertEqual(service.target.address, self.device.address)
        self.assertTrue(service.get_status().ready)

    async def test_disconnect_supersedes_in_flight_gatt_connection(self):
        connect_started = asyncio.Event()
        release_connect = asyncio.Event()

        class BlockingClient(FakeClient):
            async def connect(self, *_args, **_kwargs) -> None:
                self.calls.append("connect")
                connect_started.set()
                await release_connect.wait()
                self.is_connected = True

        def blocking_factory(target):
            client = BlockingClient(target)
            self.clients.append(client)
            return client

        self.client_factory = blocking_factory
        service = self.make_service([], auto=False)
        await service.start()
        operation = await service.connect(self.device)
        await connect_started.wait()
        await service.disconnect()
        release_connect.set()
        await asyncio.sleep(FAST_SETTINGS.auto_discovery_interval_seconds * 2)

        status = service.get_status()
        self.assertEqual(status.phase, ConnectionPhase.DISCONNECTED)
        self.assertFalse(status.desired_connected)
        self.assertFalse(status.connected)
        self.assertFalse(status.ready)
        self.assertEqual(
            service.get_operation(operation.operation_id).state,
            OperationState.CANCELLED,
        )

    async def test_disconnection_callback_immediately_starts_recovery(self):
        reconnect_connect_started = asyncio.Event()
        release_reconnect = asyncio.Event()

        class ReconnectClient(FakeClient):
            async def connect(self, *_args, **_kwargs) -> None:
                self.calls.append("connect")
                reconnect_connect_started.set()
                await release_reconnect.wait()
                self.is_connected = True

        def callback_factory(target):
            client = (
                FakeClient(target)
                if not self.clients
                else ReconnectClient(target)
            )
            self.clients.append(client)
            return client

        self.client_factory = callback_factory
        service = self.make_service([self.device])
        await service.start()
        await wait_until(lambda: service.is_ready)
        first_client = self.clients[0]
        first_client.is_connected = False
        first_client.disconnected_callback(first_client)
        await reconnect_connect_started.wait()

        status = service.get_status()
        self.assertEqual(status.phase, ConnectionPhase.CONNECTING)
        self.assertFalse(status.connected)
        self.assertFalse(status.ready)
        self.assertTrue(status.desired_connected)
        self.assertEqual(status.attempt_id, 2)
        # The Windows bond was verified by the first connection in this
        # process. Reopening its temporary WinRT pairing handle here used to
        # race teardown of the old GATT session after a hardware power cycle.
        self.assertNotIn("pair", self.clients[1].calls)
        release_reconnect.set()
        await wait_until(lambda: service.is_ready)
        self.assertIn("authenticate", self.clients[1].calls)

    async def test_event_callback_cannot_stall_authoritative_state(self):
        connected_event_started = asyncio.Event()
        release_event = asyncio.Event()

        async def event_handler(event):
            status = event.get("status")
            if status is not None and status.phase is ConnectionPhase.CONNECTED:
                connected_event_started.set()
                await release_event.wait()

        async def discover(*, timeout):
            return [self.device]

        service = ThermometerBleService(
            database=self.database,
            client_factory=self.client_factory,
            discover=discover,
            event_handler=event_handler,
            settings=FAST_SETTINGS,
            credential_registry=self.credentials,
        )
        self.services.append(service)
        await service.start()
        await connected_event_started.wait()

        status = service.get_status()
        self.assertEqual(status.phase, ConnectionPhase.CONNECTED)
        self.assertTrue(status.connected)
        self.assertTrue(status.ready)
        release_event.set()


if __name__ == "__main__":
    unittest.main()
