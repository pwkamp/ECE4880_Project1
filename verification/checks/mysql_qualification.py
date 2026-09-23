"""Disposable MySQL 8.4 qualification fixture and live schema checks."""

from __future__ import annotations

import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "backend" / "database" / "schema.sql"


def _docker(*args: str, input_text: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], input=input_text, capture_output=True, text=True, timeout=timeout, check=False)


@contextmanager
def isolated_mysql() -> Iterator[str]:
    name = f"ece4880-qualification-{os.getpid()}-{int(time.time())}"
    started = _docker("run", "--detach", "--rm", "--name", name, "-e", "MYSQL_ROOT_PASSWORD=qualification-only", "-e", "TZ=UTC", "mysql:8.4", "--default-time-zone=+00:00", timeout=120)
    if started.returncode:
        raise RuntimeError(started.stderr.strip() or "could not start isolated MySQL")
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            # mysqladmin ping reports the server alive even when credentials
            # are not ready yet. Require an authenticated query before
            # loading the schema so container initialization cannot race us.
            ready = _docker(
                "exec",
                name,
                "mysql",
                "-uroot",
                "-pqualification-only",
                "--batch",
                "--skip-column-names",
                "-e",
                "SELECT 1",
            )
            if ready.returncode == 0 and ready.stdout.strip() == "1":
                break
            time.sleep(1)
        else:
            raise RuntimeError("isolated MySQL did not become healthy")
        schema = SCHEMA.read_text(encoding="utf-8")
        loaded = _docker("exec", "-i", name, "mysql", "-uroot", "-pqualification-only", input_text=schema, timeout=60)
        if loaded.returncode:
            raise RuntimeError(loaded.stderr.strip() or "schema initialization failed")
        yield name
    finally:
        _docker("rm", "--force", name, timeout=30)


def query(name: str, sql: str, *, database: str | None = None) -> list[list[str]]:
    args = ["exec", name, "mysql", "-uroot", "-pqualification-only", "--batch", "--raw", "--skip-column-names"]
    if database:
        args.extend([database])
    args.extend(["-e", sql])
    result = _docker(*args, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"query failed: {sql}")
    return [line.split("\t") for line in result.stdout.splitlines() if line]


def execute_script(name: str, sql: str, *, database: str | None = None) -> None:
    """Execute bulk SQL over stdin to avoid Windows command-line limits."""

    args = ["exec", "-i", name, "mysql", "-uroot", "-pqualification-only"]
    if database:
        args.append(database)
    result = _docker(*args, input_text=sql, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "bulk SQL execution failed")


def db01() -> None:
    with isolated_mysql() as name:
        tables = {row[0] for row in query(name, "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='thermometer'")}
        required = {"temperature_samples", "alert_settings", "alert_recipients", "alert_rules", "alert_rule_recipients"}
        missing = required - tables
        if missing:
            raise AssertionError(f"missing tables: {sorted(missing)}")
        columns = query(name, "SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='thermometer'")
        flat = {(table, column): kind.lower() for table, column, kind in columns}
        if "users" in tables or "control_commands" in tables:
            raise AssertionError("trusted-local schema must not contain users or control_commands tables")
        assertions = {
            ("alert_recipients", "type"): "enum('email')",
            ("alert_recipients", "enabled"): "tinyint",
            ("alert_rules", "enabled"): "tinyint",
            ("temperature_samples", "observed_at_utc"): "datetime",
        }
        for key, expected in assertions.items():
            if expected not in flat.get(key, ""):
                raise AssertionError(f"{key} must contain {expected}; got {flat.get(key)}")
        query(
            name,
            "INSERT INTO alert_recipients(type,address,enabled) VALUES ('EMAIL','one@example.com',TRUE),('EMAIL','two@example.com',TRUE)",
            database="thermometer",
        )
        recipient_count = int(query(name, "SELECT COUNT(*) FROM alert_recipients WHERE type='EMAIL' AND enabled=TRUE", database="thermometer")[0][0])
        if recipient_count != 2:
            raise AssertionError(f"expected two persisted email recipients, found {recipient_count}")
        rejected_sms = _docker(
            "exec", name, "mysql", "-uroot", "-pqualification-only", "thermometer",
            "-e", "INSERT INTO alert_recipients(type,address) VALUES ('SMS','+15555550100')",
        )
        if rejected_sms.returncode == 0:
            raise AssertionError("email-only schema accepted an SMS recipient")
        timezone = query(name, "SELECT @@session.time_zone")[0][0]
        if timezone not in {"+00:00", "UTC"}:
            raise AssertionError(f"MySQL timezone is not UTC: {timezone}")


def db02() -> None:
    with isolated_mysql() as name:
        values = []
        for seq in range(700):
            values.append(f"(1,{seq},UTC_TIMESTAMP()-INTERVAL {699-seq} SECOND,20.00,'VALID',22.00,'VALID',21.00,1,'LIVE')")
        execute_script(name, "INSERT INTO temperature_samples (boot_id,sample_seq,observed_at_utc,sensor1_c,sensor1_status,sensor2_c,sensor2_status,average_c,average_valid,record_source) VALUES " + ",".join(values), database="thermometer")
        duplicate = _docker("exec", name, "mysql", "-uroot", "-pqualification-only", "thermometer", "-e", "INSERT INTO temperature_samples (boot_id,sample_seq,sensor1_status,sensor2_status,average_valid,record_source) VALUES (1,1,'MISSING','MISSING',0,'PROVISIONAL')")
        if duplicate.returncode == 0:
            raise AssertionError("duplicate boot_id/sample_seq was accepted")
        plan_rows = query(name, "EXPLAIN FORMAT=JSON SELECT * FROM temperature_samples WHERE observed_at_utc >= UTC_TIMESTAMP()-INTERVAL 300 SECOND ORDER BY observed_at_utc", database="thermometer")
        plan_text = "\n".join("\t".join(row) for row in plan_rows)
        if "entry_index" not in plan_text:
            raise AssertionError("bounded history query did not use entry_index")
        retained = int(query(name, "SELECT COUNT(*) FROM temperature_samples WHERE observed_at_utc >= UTC_TIMESTAMP()-INTERVAL 300 SECOND", database="thermometer")[0][0])
        eligible = int(query(name, "SELECT COUNT(*) FROM temperature_samples WHERE observed_at_utc < UTC_TIMESTAMP()-INTERVAL 600 SECOND", database="thermometer")[0][0])
        if retained < 299 or eligible < 90:
            raise AssertionError(f"retention fixture counts unexpected: retained={retained}, eligible={eligible}")


def db03() -> None:
    with isolated_mysql() as name:
        tables = {row[0] for row in query(name, "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='thermometer'")}
        if "control_commands" in tables:
            raise AssertionError("control_commands must be absent; commands use the direct backend API")
        if "temperature_samples" not in tables:
            raise AssertionError("temperature_samples is required as the history source")
        command_columns = query(
            name,
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='thermometer' AND COLUMN_NAME IN ('command_state','execution_state','desired_display_state')",
        )
        if int(command_columns[0][0]) != 0:
            raise AssertionError("database unexpectedly contains command-state columns")
