"""Concrete MySQL-backed implementation of ThermometerDatabaseAdapter.

Selected with THERMOMETER_DATABASE_ADAPTER_FACTORY=pc_client.mysql_adapter:create_adapter
Connection settings come from environment variables (never hardcoded):
THERMOMETER_DB_HOST, THERMOMETER_DB_PORT, THERMOMETER_DB_USER,
THERMOMETER_DB_PASSWORD, THERMOMETER_DB_NAME.

Single-device system: schema.sql has no device_id column (closed deviation,
see backend/database/README.md), so DeviceIdentity is never written here.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import aiomysql
import pymysql

from .database_adapter import (
    ConnectionStateRecord,
    DeviceIdentity,
    DisplayStateRecord,
    HistoryBatch,
    PersistenceResult,
    SampleRecord,
)
from .protocol import CONFIG

LOGGER = logging.getLogger(__name__)

_DUPLICATE_ENTRY_ERRNO = 1062

_INSERT_SAMPLE_SQL = """
    INSERT INTO temperature_samples
        (boot_id, sample_seq, sensor1_c, sensor1_status, sensor2_c, sensor2_status,
         average_c, average_valid, record_source, failure_reason)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _as_naive_utc(value: datetime) -> datetime:
    # DATETIME columns carry no timezone; DB-read values come back naive.
    # Aware values (all in-process timestamps are tz-aware UTC) must be
    # normalized the same way before either binding or comparing them.
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _sample_params(sample: SampleRecord) -> tuple:
    readings_by_id = {reading.sensor_id: reading for reading in sample.sensor_readings}
    sensor1 = readings_by_id.get(1)
    sensor2 = readings_by_id.get(2)
    if sensor1 is None or sensor2 is None:
        raise ValueError(
            f"expected sensor_readings for sensor_id 1 and 2, got "
            f"{sorted(readings_by_id)}"
        )
    average_valid = sample.average_temperature_c is not None
    return (
        sample.boot_id,
        sample.sample_sequence,
        sensor1.temperature_c,
        sensor1.status,
        sensor2.temperature_c,
        sensor2.status,
        sample.average_temperature_c,
        average_valid,
        sample.source,
        sample.failure_reason,
    )


class MySQLDatabaseAdapter:
    """Writes SampleRecords to the `thermometer` MySQL database over a pool."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        minsize: int = 1,
        maxsize: int = 5,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._minsize = minsize
        self._maxsize = maxsize
        self._pool: aiomysql.Pool | None = None

    @property
    def persistence_configured(self) -> bool:
        return True

    async def start(self) -> None:
        self._pool = await aiomysql.create_pool(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            db=self._database,
            autocommit=True,
            minsize=self._minsize,
            maxsize=self._maxsize,
        )

    async def close(self) -> None:
        if self._pool is None:
            return
        self._pool.close()
        await self._pool.wait_closed()
        self._pool = None

    def _acquire(self):
        if self._pool is None:
            raise RuntimeError(
                "MySQLDatabaseAdapter.start() was never called or failed; "
                "no connection pool is open"
            )
        return self._pool.acquire()

    async def get_last_boot_id(self, device: DeviceIdentity) -> int | None:
        # Single-device system: no device_id column to filter on, so this is
        # simply the most recent real (non-PROVISIONAL) boot_id on record.
        async with self._acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT boot_id FROM temperature_samples "
                    "WHERE boot_id IS NOT NULL ORDER BY id DESC LIMIT 1"
                )
                row = await cur.fetchone()
        return row[0] if row else None

    async def _insert_sample(self, sample: SampleRecord) -> None:
        async with self._acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(_INSERT_SAMPLE_SQL, _sample_params(sample))

    async def publish_current_sample(self, sample: SampleRecord) -> PersistenceResult:
        return await self._publish_one(sample, "current sample")

    async def publish_missing_interval(self, sample: SampleRecord) -> PersistenceResult:
        return await self._publish_one(sample, "missing interval")

    async def _publish_one(self, sample: SampleRecord, kind: str) -> PersistenceResult:
        try:
            await self._insert_sample(sample)
        except pymysql.err.IntegrityError as exc:
            if exc.args and exc.args[0] == _DUPLICATE_ENTRY_ERRNO:
                LOGGER.warning(
                    "rejected duplicate %s (boot_id=%s, sample_seq=%s)",
                    kind,
                    sample.boot_id,
                    sample.sample_sequence,
                )
                return PersistenceResult(
                    True, False, "duplicate sample rejected: boot_id/sample_seq already recorded"
                )
            raise
        return PersistenceResult(True, True)

    async def upsert_history(self, batch: HistoryBatch) -> PersistenceResult:
        # Stretch scope (SCRUM-369): a plain best-effort insert per record.
        # Re-synced ranges legitimately overlap already-stored rows, so a
        # duplicate here is expected and skipped rather than treated as a
        # persistence failure; a genuine write error still propagates.
        inserted = 0
        duplicates = 0
        for sample in batch.samples:
            try:
                await self._insert_sample(sample)
                inserted += 1
            except pymysql.err.IntegrityError as exc:
                if exc.args and exc.args[0] == _DUPLICATE_ENTRY_ERRNO:
                    duplicates += 1
                    continue
                raise
        return PersistenceResult(
            True,
            inserted > 0,
            f"history batch: {inserted} inserted, {duplicates} already present",
        )

    async def reconcile_provisional_intervals(
        self, batch: HistoryBatch
    ) -> PersistenceResult:
        # PROVISIONAL rows are stored with NULL boot_id/sample_seq by design
        # (see schema.sql), so they can't be matched to a recovered HISTORY
        # sample via the natural key. Instead: a PROVISIONAL row is stale iff
        # a HISTORY sample from this batch landed within half a sample
        # period of its observed_at_utc — that HISTORY row (already written
        # by upsert_history, which the persistence worker always runs first)
        # is strictly better data for the same real-world second, so the
        # placeholder is deleted rather than merged/updated in place.
        if not batch.samples:
            return PersistenceResult(True, False, "no history samples to reconcile against")

        tolerance = timedelta(seconds=CONFIG.device.sample_period_ms / 1000.0 / 2)
        sample_times = sorted(
            _as_naive_utc(sample.observed_at_utc) for sample in batch.samples
        )
        window_start = sample_times[0] - tolerance
        window_end = sample_times[-1] + tolerance

        async with self._acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, observed_at_utc FROM temperature_samples "
                    "WHERE record_source = 'PROVISIONAL' AND observed_at_utc BETWEEN %s AND %s",
                    (window_start, window_end),
                )
                candidates = await cur.fetchall()

                stale_ids = [
                    row_id
                    for row_id, observed_at in candidates
                    if any(
                        abs((observed_at - sample_time).total_seconds())
                        <= tolerance.total_seconds()
                        for sample_time in sample_times
                    )
                ]
                if stale_ids:
                    placeholders = ",".join(["%s"] * len(stale_ids))
                    await cur.execute(
                        f"DELETE FROM temperature_samples "
                        f"WHERE record_source = 'PROVISIONAL' AND id IN ({placeholders})",
                        tuple(stale_ids),
                    )

        return PersistenceResult(
            True,
            bool(stale_ids),
            f"removed {len(stale_ids)} provisional row(s) superseded by recovered history",
        )

    async def publish_connection_state(
        self, state: ConnectionStateRecord
    ) -> PersistenceResult:
        # No connection_state table exists yet; open scope question in
        # backend/database/README.md ("Scope questions" section).
        return PersistenceResult(
            True, False, "no connection_state table; scope decision pending"
        )

    async def publish_display_result(
        self, result: DisplayStateRecord
    ) -> PersistenceResult:
        # No display_result table exists yet; same open scope question.
        return PersistenceResult(
            True, False, "no display_result table; scope decision pending"
        )


def create_adapter() -> MySQLDatabaseAdapter:
    """Factory read by database_adapter.load_database_adapter()."""

    return MySQLDatabaseAdapter(
        host=os.environ.get("THERMOMETER_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("THERMOMETER_DB_PORT", "3306")),
        user=os.environ.get("THERMOMETER_DB_USER", "root"),
        password=os.environ.get("THERMOMETER_DB_PASSWORD", ""),
        database=os.environ.get("THERMOMETER_DB_NAME", "thermometer"),
    )
