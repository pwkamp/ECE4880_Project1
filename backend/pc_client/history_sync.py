"""Budgeted, priority-aware history retrieval.

This module knows how to retrieve and timestamp history, but it deliberately
does not know about connection state, REST operations, or database adapters.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from .ble_scheduler import RequestPriority
from .protocol import (
    CONFIG,
    CurrentSnapshot,
    HistoryChunk,
    ProtocolError,
    ServiceConfig,
)
from .thermometer_client import HistorySync, TimedHistoryRecord, describe_ble_error


@dataclass(frozen=True)
class HistoryRetrieval:
    history: HistorySync
    deadline: float
    failures: tuple[str, ...]


class HistorySynchronizer:
    """Retrieve recent records round-robin until complete or out of budget."""

    def __init__(
        self,
        *,
        settings: Callable[[], ServiceConfig],
        monotonic: Callable[[], float],
        utc_now: Callable[[], datetime],
        sleep: Callable[[float], Awaitable[None]],
        client: Callable[[], Any],
        submit: Callable[
            [RequestPriority, str, Callable[[], Awaitable[Any]]], Awaitable[Any]
        ],
        current_anchor: Callable[[], tuple[CurrentSnapshot | None, datetime | None]],
        publish_current: Callable[[CurrentSnapshot, datetime], Awaitable[Any]],
    ) -> None:
        self._settings = settings
        self._monotonic = monotonic
        self._utc_now = utc_now
        self._sleep = sleep
        self._client = client
        self._submit = submit
        self._current_anchor = current_anchor
        self._publish_current = publish_current

    async def synchronize(self, operation: Any) -> HistoryRetrieval:
        # History synchronization rule: metadata first, recent-first chunks,
        # round-robin sensors, bounded retries, and one overall time budget.
        settings = self._settings()
        started = self._monotonic()
        deadline = started + settings.history_sync_budget_seconds
        meta = await self._call(
            "history metadata",
            lambda: self._client().get_history_meta(),
            deadline,
        )
        expected = tuple(meta.counts)
        retrieved = [0 for _ in expected]
        records: dict[tuple[int, int], Any] = {}
        pending: deque[int] = deque(
            sensor_id
            for sensor_id, count in enumerate(expected, start=1)
            if count > 0
        )
        remaining = {sensor_id: expected[sensor_id - 1] for sensor_id in pending}
        newest = {
            sensor_id: (
                meta.oldest_sequences[sensor_id - 1]
                + expected[sensor_id - 1]
                - 1
            )
            & 0xFFFFFFFF
            for sensor_id in pending
        }
        failures: list[str] = []
        total_expected = sum(expected)
        budget_expired = False

        while pending and self._monotonic() < deadline:
            sensor_id = pending.popleft()
            request_count = min(
                self._client().records_per_chunk(), remaining[sensor_id]
            )
            start_sequence = (newest[sensor_id] - request_count + 1) & 0xFFFFFFFF
            chunk: HistoryChunk | None = None
            last_error: Exception | None = None
            for _attempt in range(settings.history_chunk_retry_count + 1):
                try:
                    chunk = await self._call(
                        f"sensor {sensor_id} history chunk",
                        lambda sid=sensor_id, start=start_sequence, count=request_count: (
                            self._client().get_history_chunk(sid, start, count)
                        ),
                        deadline,
                    )
                    self.validate_chunk(
                        chunk, sensor_id, start_sequence, request_count
                    )
                    break
                except asyncio.TimeoutError:
                    budget_expired = True
                    break
                except Exception as exc:
                    last_error = exc
            if budget_expired:
                break
            if chunk is None:
                failures.append(
                    f"sensor {sensor_id}: "
                    f"{describe_ble_error(last_error or RuntimeError('unknown history error'))}"
                )
                continue

            for record in chunk.records:
                records[(sensor_id, record.sequence)] = record
            retrieved[sensor_id - 1] += len(chunk.records)
            remaining[sensor_id] -= len(chunk.records)
            newest[sensor_id] = (start_sequence - 1) & 0xFFFFFFFF
            operation.progress = (
                sum(retrieved) / total_expected if total_expected else 1.0
            )
            operation.updated_at_utc = self._utc_now()
            if remaining[sensor_id] > 0:
                pending.append(sensor_id)
            # Give display/current requests a scheduling point between chunks.
            await self._sleep(0)

        if pending or budget_expired:
            failures.append("history synchronization exceeded its time budget")

        anchor, anchor_time = self._current_anchor()
        if self._monotonic() < deadline:
            try:
                anchor = await self._call(
                    "history time anchor",
                    lambda: self._client().get_current(),
                    deadline,
                    priority=RequestPriority.CURRENT,
                )
                anchor_time = self._utc_now()
                await self._publish_current(anchor, anchor_time)
            except Exception as exc:
                failures.append(f"time anchor: {describe_ble_error(exc)}")

        if anchor is None or anchor_time is None:
            raise RuntimeError("no current snapshot is available as a history anchor")
        if anchor.boot_id != meta.boot_id:
            failures.append("device rebooted during history synchronization")

        sample_seconds = CONFIG.device.sample_period_ms / 1000.0
        timed_records = tuple(
            TimedHistoryRecord(
                sensor_id=sensor_id,
                sequence=record.sequence,
                sampled_at=self.timestamp(
                    anchor.newest_sequence,
                    anchor_time,
                    record.sequence,
                    sample_seconds,
                ),
                temperature_c=record.temperature_c,
                data_status=record.data_status,
            )
            for (sensor_id, _sequence), record in records.items()
        )
        elapsed = self._monotonic() - started
        complete = tuple(retrieved) == expected and not failures
        history = HistorySync(
            meta=meta,
            anchor=anchor,
            records=timed_records,
            expected_counts=expected,
            retrieved_counts=tuple(retrieved),
            complete=complete,
            elapsed_seconds=elapsed,
            failure_reason="; ".join(failures) or None,
            persistence_configured=False,
        )
        return HistoryRetrieval(history, deadline, tuple(failures))

    async def _call(
        self,
        name: str,
        action: Callable[[], Awaitable[Any]],
        deadline: float,
        *,
        priority: RequestPriority = RequestPriority.HISTORY,
    ) -> Any:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise asyncio.TimeoutError
        return await asyncio.wait_for(
            self._submit(priority, name, action), timeout=remaining
        )

    @staticmethod
    def validate_chunk(
        chunk: HistoryChunk,
        sensor_id: int,
        start_sequence: int,
        requested_count: int,
    ) -> None:
        if chunk.sensor_id != sensor_id or chunk.start_sequence != start_sequence:
            raise ProtocolError("history chunk does not match its request")
        if not chunk.records or len(chunk.records) > requested_count:
            raise ProtocolError("history chunk has an invalid record count")
        expected_sequence = start_sequence
        for record in chunk.records:
            if record.sequence != expected_sequence:
                raise ProtocolError("history chunk sequence is discontinuous")
            expected_sequence = (expected_sequence + 1) & 0xFFFFFFFF

    @staticmethod
    def timestamp(
        anchor_sequence: int,
        anchor_time: datetime,
        record_sequence: int,
        sample_seconds: float,
    ) -> datetime:
        backward = (anchor_sequence - record_sequence) & 0xFFFFFFFF
        if backward <= 0x7FFFFFFF:
            return anchor_time - timedelta(seconds=backward * sample_seconds)
        forward = (record_sequence - anchor_sequence) & 0xFFFFFFFF
        return anchor_time + timedelta(seconds=forward * sample_seconds)
