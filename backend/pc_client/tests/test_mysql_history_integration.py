"""Optional real-MySQL check using an isolated, short-lived test schema."""

import os
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import pymysql

from pc_client.database_adapter import HistoryBatch, SampleRecord, SensorReading
from pc_client.mysql_adapter import MySQLDatabaseAdapter


def sample(sequence: int, sensor2: float | None, *, source: str = "HISTORY") -> SampleRecord:
    sensor1 = 21.0
    return SampleRecord(
        device=None,
        observed_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc)
        + timedelta(seconds=sequence),
        boot_id=77,
        sample_sequence=sequence,
        sensor_readings=(
            SensorReading(1, sensor1, "VALID", True),
            SensorReading(2, sensor2, "VALID" if sensor2 is not None else "NOT_RETRIEVED", True),
        ),
        average_temperature_c=(sensor1 + sensor2) / 2 if sensor2 is not None else None,
        source=source,
    )


@unittest.skipUnless(
    os.environ.get("THERMOMETER_MYSQL_INTEGRATION") == "1",
    "set THERMOMETER_MYSQL_INTEGRATION=1 to run against a local MySQL server",
)
class MySQLHistoryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_300_row_batch_merges_partial_history_without_overwriting_live(self):
        password = os.environ["MYSQL_ROOT_PASSWORD"]
        port = int(os.environ.get("MYSQL_HOST_PORT", "3306"))
        schema = f"thermometer_history_test_{uuid.uuid4().hex[:12]}"
        admin = pymysql.connect(
            host="127.0.0.1", port=port, user="root", password=password,
            autocommit=True,
        )
        created = False
        try:
            with admin.cursor() as cursor:
                cursor.execute("SHOW DATABASES LIKE %s", (schema,))
                self.assertIsNone(cursor.fetchone())
                cursor.execute(f"CREATE DATABASE `{schema}`")
                created = True
                cursor.execute(f"""
                    CREATE TABLE `{schema}`.temperature_samples (
                        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        boot_id INT UNSIGNED, sample_seq INT UNSIGNED,
                        observed_at_utc DATETIME NOT NULL,
                        sensor1_c DECIMAL(5,2),
                        sensor1_status ENUM('VALID','DISCONNECTED','NOT_RETRIEVED','MISSING') NOT NULL,
                        sensor2_c DECIMAL(5,2),
                        sensor2_status ENUM('VALID','DISCONNECTED','NOT_RETRIEVED','MISSING') NOT NULL,
                        average_c DECIMAL(5,2), average_valid BOOLEAN NOT NULL,
                        record_source ENUM('LIVE','HISTORY','PROVISIONAL') NOT NULL,
                        failure_reason VARCHAR(255),
                        UNIQUE KEY uq_sample (boot_id, sample_seq)
                    )
                """)

            adapter = MySQLDatabaseAdapter(
                host="127.0.0.1", port=port, user="root", password=password,
                database=schema,
            )
            await adapter.start()
            try:
                await adapter.publish_current_sample(sample(1, 22.0, source="LIVE"))
                partial = HistoryBatch(None, 77, None, False, (sample(2, None),),
                                       (1, 1), (1, 0), False, 0.1, None)
                await adapter.upsert_history(partial)
                recovered = HistoryBatch(
                    None, 77, None, False,
                    tuple(sample(sequence, 23.0) for sequence in range(1, 301)),
                    (300, 300), (300, 300), True, 5.0, None,
                )
                started = time.monotonic()
                result = await adapter.upsert_history(recovered)
                elapsed = time.monotonic() - started
                self.assertTrue(result.persisted)
                self.assertLess(elapsed, 10.0)
            finally:
                await adapter.close()

            with admin.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) FROM `{schema}`.temperature_samples"
                )
                self.assertEqual(cursor.fetchone()[0], 300)
                cursor.execute(f"""
                    SELECT record_source, sensor2_c, sensor2_status,
                           average_c, average_valid
                    FROM `{schema}`.temperature_samples WHERE sample_seq = 1
                """)
                live = cursor.fetchone()
                self.assertEqual(live[0], "LIVE")
                self.assertEqual(float(live[1]), 22.0)
                cursor.execute(f"""
                    SELECT record_source, sensor2_c, sensor2_status,
                           average_c, average_valid
                    FROM `{schema}`.temperature_samples WHERE sample_seq = 2
                """)
                merged = cursor.fetchone()
                self.assertEqual(merged[0], "HISTORY")
                self.assertEqual(float(merged[1]), 23.0)
                self.assertEqual(merged[2], "VALID")
                self.assertEqual(float(merged[3]), 22.0)
                self.assertEqual(merged[4], 1)
        finally:
            if created and schema.startswith("thermometer_history_test_"):
                with admin.cursor() as cursor:
                    cursor.execute(f"DROP DATABASE `{schema}`")
                    cursor.execute("SHOW DATABASES LIKE %s", (schema,))
                    self.assertIsNone(cursor.fetchone())
            admin.close()
