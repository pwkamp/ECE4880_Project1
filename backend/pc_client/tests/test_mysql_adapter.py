import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pymysql

from pc_client.database_adapter import (
    ConnectionStateRecord,
    DisplayStateRecord,
    HistoryBatch,
    SampleRecord,
    SensorReading,
)
from pc_client.mysql_adapter import MySQLDatabaseAdapter, create_adapter


def make_sample(
    *,
    boot_id=77,
    sample_seq=10,
    source="LIVE",
    average=21.0,
    failure_reason=None,
    observed_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
) -> SampleRecord:
    return SampleRecord(
        device=None,
        observed_at_utc=observed_at_utc,
        boot_id=boot_id,
        sample_sequence=sample_seq,
        sensor_readings=(
            SensorReading(1, 20.0, "VALID", True),
            SensorReading(2, 22.0, "VALID", True),
        ),
        average_temperature_c=average,
        source=source,
        provisional=source == "PROVISIONAL",
        failure_reason=failure_reason,
    )


class _FakeCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None, raise_on_execute=None):
        self.executed = []
        self._fetchone_result = fetchone_result
        self._fetchall_result = fetchall_result or []
        self._raise_on_execute = raise_on_execute

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self._raise_on_execute is not None:
            raise self._raise_on_execute

    async def fetchone(self):
        return self._fetchone_result

    async def fetchall(self):
        return self._fetchall_result


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def cursor(self):
        return self._cursor


class _FakePool:
    def __init__(self, connection: _FakeConnection):
        self._connection = connection

    def acquire(self):
        return self._connection

    def close(self):
        pass

    async def wait_closed(self):
        pass


def make_adapter_with_cursor(cursor: _FakeCursor) -> MySQLDatabaseAdapter:
    adapter = MySQLDatabaseAdapter(
        host="localhost", port=3306, user="u", password="p", database="thermometer"
    )
    adapter._pool = _FakePool(_FakeConnection(cursor))
    return adapter


class MySQLAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_current_sample_inserts_with_expected_params(self) -> None:
        cursor = _FakeCursor()
        adapter = make_adapter_with_cursor(cursor)

        result = await adapter.publish_current_sample(make_sample())

        self.assertTrue(result.configured)
        self.assertTrue(result.persisted)
        sql, params = cursor.executed[0]
        self.assertIn("INSERT INTO temperature_samples", sql)
        self.assertEqual(
            params,
            (77, 10, 20.0, "VALID", 22.0, "VALID", 21.0, True, "LIVE", None),
        )

    async def test_missing_interval_sample_has_null_average_and_failure_reason(
        self,
    ) -> None:
        cursor = _FakeCursor()
        adapter = make_adapter_with_cursor(cursor)
        sample = make_sample(
            boot_id=None,
            sample_seq=None,
            source="PROVISIONAL",
            average=None,
            failure_reason="poll timed out",
        )

        await adapter.publish_missing_interval(sample)

        _, params = cursor.executed[0]
        self.assertEqual(
            params,
            (None, None, 20.0, "VALID", 22.0, "VALID", None, False, "PROVISIONAL", "poll timed out"),
        )

    async def test_duplicate_sample_is_rejected_not_raised(self) -> None:
        duplicate_error = pymysql.err.IntegrityError(1062, "Duplicate entry")
        cursor = _FakeCursor(raise_on_execute=duplicate_error)
        adapter = make_adapter_with_cursor(cursor)

        result = await adapter.publish_current_sample(make_sample())

        self.assertTrue(result.configured)
        self.assertFalse(result.persisted)
        self.assertIn("duplicate", result.detail)

    async def test_non_duplicate_integrity_error_propagates(self) -> None:
        other_error = pymysql.err.IntegrityError(1452, "FK constraint fails")
        cursor = _FakeCursor(raise_on_execute=other_error)
        adapter = make_adapter_with_cursor(cursor)

        with self.assertRaises(pymysql.err.IntegrityError):
            await adapter.publish_current_sample(make_sample())

    async def test_get_last_boot_id_returns_none_when_no_rows(self) -> None:
        cursor = _FakeCursor(fetchone_result=None)
        adapter = make_adapter_with_cursor(cursor)

        boot_id = await adapter.get_last_boot_id(device=None)

        self.assertIsNone(boot_id)

    async def test_get_last_boot_id_returns_stored_value(self) -> None:
        cursor = _FakeCursor(fetchone_result=(42,))
        adapter = make_adapter_with_cursor(cursor)

        boot_id = await adapter.get_last_boot_id(device=None)

        self.assertEqual(boot_id, 42)

    async def test_upsert_history_counts_inserted_and_duplicate_rows(self) -> None:
        adapter = MySQLDatabaseAdapter(
            host="localhost", port=3306, user="u", password="p", database="thermometer"
        )
        calls = {"n": 0}

        async def fake_insert(sample):
            calls["n"] += 1
            if calls["n"] == 2:
                raise pymysql.err.IntegrityError(1062, "Duplicate entry")

        adapter._insert_sample = fake_insert
        batch = HistoryBatch(
            device=None,
            boot_id=77,
            previous_boot_id=None,
            new_boot=False,
            samples=(
                make_sample(sample_seq=1, source="HISTORY"),
                make_sample(sample_seq=2, source="HISTORY"),
                make_sample(sample_seq=3, source="HISTORY"),
            ),
            expected_counts=(3, 3),
            retrieved_counts=(3, 3),
            complete=True,
            elapsed_seconds=0.5,
            failure_reason=None,
        )

        result = await adapter.upsert_history(batch)

        self.assertTrue(result.persisted)
        self.assertIn("2 inserted", result.detail)
        self.assertIn("1 already present", result.detail)

    async def test_connection_state_and_display_result_are_documented_noops(
        self,
    ) -> None:
        adapter = MySQLDatabaseAdapter(
            host="localhost", port=3306, user="u", password="p", database="thermometer"
        )

        connection_result = await adapter.publish_connection_state(
            ConnectionStateRecord(None, datetime.now(timezone.utc), "phase", True, None, None)
        )
        display_result = await adapter.publish_display_result(
            DisplayStateRecord(None, datetime.now(timezone.utc), 1, True, True, "ON")
        )

        for result in (connection_result, display_result):
            self.assertTrue(result.configured)
            self.assertFalse(result.persisted)

    async def test_reconcile_with_empty_batch_is_a_noop(self) -> None:
        adapter = MySQLDatabaseAdapter(
            host="localhost", port=3306, user="u", password="p", database="thermometer"
        )
        batch = HistoryBatch(
            device=None,
            boot_id=77,
            previous_boot_id=None,
            new_boot=False,
            samples=(),
            expected_counts=(0, 0),
            retrieved_counts=(0, 0),
            complete=True,
            elapsed_seconds=0.0,
            failure_reason=None,
        )

        result = await adapter.reconcile_provisional_intervals(batch)

        self.assertTrue(result.configured)
        self.assertFalse(result.persisted)

    async def test_reconcile_deletes_provisional_rows_matched_by_history_timestamp(
        self,
    ) -> None:
        anchor = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        anchor_naive = anchor.replace(tzinfo=None)  # DATETIME columns read back naive
        cursor = _FakeCursor(
            fetchall_result=[
                (101, anchor_naive),  # matches a recovered HISTORY sample: stale
                (102, anchor_naive + timedelta(seconds=5)),  # no matching sample: keep
            ]
        )
        adapter = make_adapter_with_cursor(cursor)
        batch = HistoryBatch(
            device=None,
            boot_id=77,
            previous_boot_id=None,
            new_boot=False,
            samples=(make_sample(sample_seq=1, source="HISTORY", observed_at_utc=anchor),),
            expected_counts=(1, 1),
            retrieved_counts=(1, 1),
            complete=True,
            elapsed_seconds=0.1,
            failure_reason=None,
        )

        result = await adapter.reconcile_provisional_intervals(batch)

        self.assertTrue(result.persisted)
        self.assertIn("removed 1 provisional", result.detail)
        select_sql, _ = cursor.executed[0]
        self.assertIn("SELECT id, observed_at_utc", select_sql)
        delete_sql, delete_params = cursor.executed[1]
        self.assertIn("DELETE FROM temperature_samples", delete_sql)
        self.assertIn("record_source = 'PROVISIONAL'", delete_sql)
        self.assertEqual(delete_params, (101,))

    async def test_reconcile_deletes_nothing_when_no_timestamps_match(self) -> None:
        anchor = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        anchor_naive = anchor.replace(tzinfo=None)
        cursor = _FakeCursor(
            fetchall_result=[(101, anchor_naive + timedelta(seconds=30))]
        )
        adapter = make_adapter_with_cursor(cursor)
        batch = HistoryBatch(
            device=None,
            boot_id=77,
            previous_boot_id=None,
            new_boot=False,
            samples=(make_sample(sample_seq=1, source="HISTORY", observed_at_utc=anchor),),
            expected_counts=(1, 1),
            retrieved_counts=(1, 1),
            complete=True,
            elapsed_seconds=0.1,
            failure_reason=None,
        )

        result = await adapter.reconcile_provisional_intervals(batch)

        self.assertFalse(result.persisted)
        self.assertEqual(len(cursor.executed), 1)  # SELECT only, no DELETE issued


class CreateAdapterTests(unittest.TestCase):
    def test_reads_settings_from_environment(self) -> None:
        env = {
            "THERMOMETER_DB_HOST": "db.internal",
            "THERMOMETER_DB_PORT": "3307",
            "THERMOMETER_DB_USER": "svc",
            "THERMOMETER_DB_PASSWORD": "secret",
            "THERMOMETER_DB_NAME": "thermometer_test",
        }
        with patch.dict(os.environ, env, clear=True):
            adapter = create_adapter()

        self.assertEqual(adapter._host, "db.internal")
        self.assertEqual(adapter._port, 3307)
        self.assertEqual(adapter._user, "svc")
        self.assertEqual(adapter._password, "secret")
        self.assertEqual(adapter._database, "thermometer_test")

    def test_defaults_when_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            adapter = create_adapter()

        self.assertEqual(adapter._host, "127.0.0.1")
        self.assertEqual(adapter._port, 3306)
        self.assertEqual(adapter._user, "root")
        self.assertEqual(adapter._database, "thermometer")


if __name__ == "__main__":
    unittest.main()
