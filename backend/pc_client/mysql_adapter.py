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

LOGGER = logging.getLogger(__name__)

_DUPLICATE_ENTRY_ERRNO = 1062

_INSERT_SAMPLE_SQL = """
    INSERT INTO temperature_samples
        (boot_id, sample_seq, sensor1_c, sensor1_status, sensor2_c, sensor2_status,
         average_c, average_valid, record_source, failure_reason)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


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
        # Deferred to SCRUM-369: PROVISIONAL rows are stored with NULL
        # boot_id/sample_seq by design (see schema.sql), so matching them to
        # a specific finalized HISTORY sample needs a real strategy (e.g. an
        # observed_at_utc window match), not a natural-key upsert. Left as a
        # documented no-op rather than a heuristic that could silently
        # mutate the wrong row.
        return PersistenceResult(
            True, False, "provisional reconciliation deferred to SCRUM-369; no-op"
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
