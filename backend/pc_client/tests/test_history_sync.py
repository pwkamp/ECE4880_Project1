"""Regression coverage for a full, actively rotating ESP32 history ring."""

import asyncio
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from pc_client.history_sync import HistorySynchronizer
from pc_client.protocol import (
    CONFIG,
    CurrentSnapshot,
    DataStatus,
    HistoryChunk,
    HistoryMeta,
    HistoryRecordValue,
    ProtocolError,
    SensorSnapshot,
    Status,
    VisibleState,
)


class RotatingRingClient:
    def __init__(self, clock):
        self.clock = clock
        self.requests = []

    async def get_history_meta(self):
        return HistoryMeta(77, 300, (300, 300), (1, 1))

    def records_per_chunk(self):
        return 32

    async def get_history_chunk(self, sensor_id, start_sequence, count):
        # Simulate a full ring that overwrites one old record every second.
        if start_sequence <= int(self.clock[0]):
            raise ProtocolError(
                "requested history has already been overwritten",
                Status.NOT_AVAILABLE,
            )
        self.requests.append((sensor_id, start_sequence, count))
        self.clock[0] += 0.25
        return HistoryChunk(
            sensor_id,
            start_sequence,
            tuple(
                HistoryRecordValue(sequence, 20.0 + sensor_id, DataStatus.VALID)
                for sequence in range(start_sequence, start_sequence + count)
            ),
        )

    async def get_current(self):
        sequence = 300 + int(self.clock[0])
        sensors = tuple(
            SensorSnapshot(sensor_id, 20.0 + sensor_id, VisibleState.ON, True)
            for sensor_id in (1, 2)
        )
        return CurrentSnapshot(77, sequence, sensors, 21.5)


class HistorySyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_compact_72_record_transfer_can_fit_five_second_target(self):
        clock = [0.0]
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)

        class CompactClient(RotatingRingClient):
            def records_per_chunk(self):
                return 72

            async def get_history_chunk(self, sensor_id, start_sequence, count):
                result = await super().get_history_chunk(sensor_id, start_sequence, count)
                clock[0] += 0.2  # 450 ms total per GATT write/read exchange
                return result

        client = CompactClient(clock)

        async def submit(_priority, _name, action):
            return await action()

        async def publish_current(_snapshot, _observed_at):
            return None

        synchronizer = HistorySynchronizer(
            settings=lambda: replace(CONFIG.service, history_sync_budget_seconds=10.0),
            monotonic=lambda: clock[0],
            utc_now=lambda: epoch + timedelta(seconds=clock[0]),
            sleep=asyncio.sleep,
            client=lambda: client,
            submit=submit,
            current_anchor=lambda: (CurrentSnapshot(77, 300, (), None), epoch),
            publish_current=publish_current,
        )
        result = await synchronizer.synchronize(
            SimpleNamespace(progress=0.0, updated_at_utc=None)
        )
        self.assertTrue(result.history.complete, result.history.failure_reason)
        self.assertEqual(len(client.requests), 10)
        self.assertLess(result.history.elapsed_seconds, 5.0)

    async def test_budget_expiry_keeps_partial_rows_and_initial_anchor(self):
        clock = [0.0]
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)

        class NoLateCurrentClient(RotatingRingClient):
            async def get_current(self):
                raise AssertionError("a late current read must not be required")

        client = NoLateCurrentClient(clock)

        async def submit(_priority, _name, action):
            return await action()

        async def publish_current(_snapshot, _observed_at):
            return None

        synchronizer = HistorySynchronizer(
            settings=lambda: replace(CONFIG.service, history_sync_budget_seconds=0.7),
            monotonic=lambda: clock[0],
            utc_now=lambda: epoch + timedelta(seconds=clock[0]),
            sleep=asyncio.sleep,
            client=lambda: client,
            submit=submit,
            current_anchor=lambda: (CurrentSnapshot(77, 300, (), None), epoch),
            publish_current=publish_current,
        )
        result = await synchronizer.synchronize(
            SimpleNamespace(progress=0.0, updated_at_utc=None)
        )
        self.assertFalse(result.history.complete)
        self.assertGreater(len(result.history.records), 0)
        self.assertIn("time budget", result.history.failure_reason)

    async def test_full_rotating_ring_recovers_all_300_seconds_within_budget(self):
        clock = [0.0]
        client = RotatingRingClient(clock)
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)

        async def submit(_priority, _name, action):
            return await action()

        async def publish_current(_snapshot, _observed_at):
            return None

        synchronizer = HistorySynchronizer(
            settings=lambda: replace(CONFIG.service, history_sync_budget_seconds=10.0),
            monotonic=lambda: clock[0],
            utc_now=lambda: epoch + timedelta(seconds=clock[0]),
            sleep=asyncio.sleep,
            client=lambda: client,
            submit=submit,
            current_anchor=lambda: (None, None),
            publish_current=publish_current,
        )

        result = await synchronizer.synchronize(
            SimpleNamespace(progress=0.0, updated_at_utc=None)
        )

        self.assertTrue(result.history.complete, result.history.failure_reason)
        self.assertEqual(result.history.retrieved_counts, (300, 300))
        self.assertEqual(len(result.history.records), 600)
        self.assertEqual(client.requests[:2], [(1, 1, 32), (2, 1, 32)])
        self.assertLessEqual(result.history.elapsed_seconds, 10.0)
        self.assertEqual(
            min(record.sampled_at for record in result.history.records),
            epoch - timedelta(seconds=299),
        )

    async def test_old_firmware_salvages_surviving_rows_after_ring_advances(self):
        clock = [0.0]

        class AdvancingClient(RotatingRingClient):
            def __init__(self):
                super().__init__(clock)
                self.meta_calls = 0

            async def get_history_meta(self):
                self.meta_calls += 1
                if self.meta_calls == 1:
                    clock[0] = 4.0
                    return HistoryMeta(77, 300, (300, 300), (1, 1))
                return HistoryMeta(77, 304, (300, 300), (5, 5))

        client = AdvancingClient()
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)

        async def submit(_priority, _name, action):
            return await action()

        async def publish_current(_snapshot, _observed_at):
            return None

        synchronizer = HistorySynchronizer(
            settings=lambda: replace(CONFIG.service, history_sync_budget_seconds=10.0),
            monotonic=lambda: clock[0],
            utc_now=lambda: epoch + timedelta(seconds=clock[0]),
            sleep=asyncio.sleep,
            client=lambda: client,
            submit=submit,
            current_anchor=lambda: (None, None),
            publish_current=publish_current,
        )

        result = await synchronizer.synchronize(
            SimpleNamespace(progress=0.0, updated_at_utc=None)
        )

        self.assertFalse(result.history.complete)
        self.assertEqual(result.history.retrieved_counts, (296, 296))
        self.assertEqual(len(result.history.records), 592)
        self.assertIn("overwritten", result.history.failure_reason)
