# Database Module

MySQL storage for the temperature monitoring system. Owns the `thermometer`
database and its tables: `temperature_samples` (SCRUM-371) plus the user and
alert configuration tables (SCRUM-372).

## Build

Run against a local MySQL server:

```
mysql -u root -p < schema.sql
```

`schema.sql` is re-runnable. It drops and recreates the `thermometer` database,
so it wipes existing data on every run.

The MySQL server timezone must be set to UTC (see "Timestamp handling"). This is
a per-machine server setting, not part of this file.

## Tables

| Table | Purpose | Requirement |
|---|---|---|
| `temperature_samples` | One row per 1 Hz poll: both probes, computed average, per-sensor status | SWE-DB-LLR-550 |
| `users` | Web app accounts: username, password hash, role, enabled state | SWE-DB-LLR-554 |
| `alert_recipients` | Alert destinations: EMAIL or SMS address | SWE-DB-LLR-555 |
| `alert_rules` | Threshold rules with messages and monitored series | SWE-DB-LLR-556 |
| `alert_rule_recipients` | Junction linking rules to recipients (many-to-many) | SWE-DB-LLR-556 |

Rows in `temperature_samples` arrive from the BLE connection service through the
database adapter. The user and alert tables are consumed by the web application
(not yet built); the schema is the contract.

`temperature_samples` also has a nullable `failure_reason VARCHAR(255)` column
(SCRUM-341), populated for `PROVISIONAL` rows with why the 1 Hz slot was
missed. It has no dedicated requirement ID yet; it exists to give the
`SampleRecord.failure_reason` field a destination column since the BLE
connector actively populates it.

## Traceability

| Piece | Requirement |
|---|---|
| temperature_samples column set | SWE-DB-LLR-550 |
| Sample uniqueness | SWE-DB-LLR-551 |
| Time-window / latest-sample index | SWE-DB-LLR-552 |
| Celsius storage | SWE-DB-LLR-559 |
| UTC timestamps | SWE-DB-LLR-560 |
| Series + status model | SWE-DB-MLR-551 |
| Configuration + authorization storage | SWE-DB-MLR-552 |
| users table | SWE-DB-LLR-554 |
| alert_recipients table | SWE-DB-LLR-555 |
| alert_rules table | SWE-DB-LLR-556 |

## Key design decisions

### temperature_samples

- **Surrogate primary key.** `id BIGINT UNSIGNED AUTO_INCREMENT` is the primary
  key. The natural sample key `(boot_id, sample_seq)` is a `UNIQUE` constraint,
  not the primary key, because missing-interval (`PROVISIONAL`) rows arrive with
  `boot_id` and `sample_seq` both NULL, and primary key columns cannot be NULL.
  `UNIQUE` still rejects duplicate real samples, and because MySQL treats NULLs
  as non-equal, multiple `PROVISIONAL` rows coexist without collision.
- **`boot_id` is `INT UNSIGNED`.** Firmware generates it with `esp_random()` as a
  full 32-bit value, so the column must hold the full `u32` range. Random 32-bit
  boot ids make cross-session key collisions negligible.
- **Nullable value columns.** `sensor1_c`, `sensor2_c`, and `average_c` are NULL
  when the reading is not trustworthy. Status columns are NOT NULL: a reading
  always has a state.
- **`average_c` is NULL unless both probes are valid.** The service computes the
  average only when both sensor readings are valid; a single valid probe yields
  NULL, not a one-probe average.
- **`DECIMAL(5,2)` Celsius**, matching the `i16` centi-Celsius wire format and
  sized to the sensor's physical range.
- **`DATETIME`, not `TIMESTAMP`.** Stores the value with no timezone conversion;
  UTC correctness depends on the server timezone.
- **No `device_id` (decided).** SWE-DB-LLR-550 names a `device_id` field, but the
  system is single-device by design and will not support more than one box. The
  adapter identifies the device by BLE address and advertised name, so a
  `device_id` column would hold no distinguishing information. It is omitted; this
  is a closed deviation, not an open question.

### users / alerts

- **Surrogate primary key on every table**, mirroring `temperature_samples`.
- **`role` is `ENUM('USER','ADMIN')`.** ADMIN accounts may perform third-box
  control and alert configuration; USER accounts are read-only.
- **No plaintext passwords.** `password_hash VARCHAR(255)` holds a hashed value
  only, sized for bcrypt / Argon2id / scrypt PHC strings.
- **`enabled` defaults TRUE.** New accounts are active on creation.
- **Multiple recipients per type.** `alert_recipients` has no uniqueness on
  `(type, address)`, so several EMAIL and several SMS recipients coexist.
- **Rule/recipient link is many-to-many.** A rule can notify several recipients
  and a recipient can serve several rules, so the link is a junction table
  (`alert_rule_recipients`) rather than a column. Both foreign keys are
  `ON DELETE CASCADE`: deleting a rule or a recipient removes its links but not
  the other party.
- **Thresholds are `DECIMAL(5,2)` Celsius**, matching `temperature_samples`. Both
  `min_threshold` and `max_threshold` are required (every rule is a bounded band
  with a message for each side).
- **`monitored_series` is `ENUM('SENSOR1','SENSOR2','AVERAGE')`**, mapping to the
  three series in `temperature_samples`.

## Timestamp handling

- All timestamps are UTC per SWE-DB-LLR-560. The MySQL server timezone must be
  set to UTC (`default-time-zone='+00:00'` in `my.ini`, then restart) so that
  `DEFAULT CURRENT_TIMESTAMP` and any application-supplied times are consistent.
  Verify with `SELECT @@global.time_zone;` (expect `+00:00`).
- `observed_at_utc` for `LIVE` rows is stamped by the database on insert. The
  wire protocol carries no firmware timestamp (the ESP32 has no real-time clock).
- `HISTORY` rows are backfilled; their timestamps are reconstructed by the
  service from a live anchor and the 1 Hz sample period, so they are
  PC-clock-derived, not device-observed.
- `created_at_utc` / `updated_at_utc` on the user and alert tables use
  `DEFAULT CURRENT_TIMESTAMP`; `updated_at_utc` also carries
  `ON UPDATE CURRENT_TIMESTAMP` so it re-stamps on every edit.

### Local server setup (per machine, for testing)

This is not part of the schema and must be repeated on every machine that runs
a MySQL server against this schema:

- **Persistent (survives restart):** add `default-time-zone='+00:00'` under
  `[mysqld]` in the server's config file (`my.ini` on Windows, `my.cnf` on
  Linux/macOS), then restart the MySQL service.
- **Session-only (quick local testing, does not survive restart):**
  `SET GLOBAL time_zone = '+00:00';` against a running server.
- **Verify either way:** `SELECT @@global.time_zone;` should return `+00:00`.

## Open items

- `boot_id` is currently a random per-boot value (firmware side). Collisions are
  negligible at 32-bit width and would fail loud (duplicate-key rejection)
  rather than silently. A persistent incrementing counter would remove the risk
  entirely; noted, not blocking.
- Provisional rows are not write-once. The adapter method
  `reconcile_provisional_intervals` implies previously-stored `PROVISIONAL` rows
  may be updated to a final state after a history sync; status and
  `average_valid` columns are therefore mutable by design. `PROVISIONAL` rows
  have NULL `boot_id`/`sample_seq`, so matching one to a specific finalized
  sample needs a real strategy (e.g. an `observed_at_utc` window), not a
  natural-key upsert; the reference adapter (`backend/pc_client/mysql_adapter.py`)
  leaves this method a documented no-op, deferred to SCRUM-369.
- Status/source vocabulary follows the implementation (decided). The schema uses
  the code's values (`VALID / DISCONNECTED / NOT_RETRIEVED / MISSING`) so the
  database and BLE service agree exactly. The approved requirement text
  (SWE-DB-MLR-551) still lists the older `unplugged-sensor / no-data / provisional
  / derived-unavailable` terms; updating that text to match the implementation is
  a requirements-doc task, not a schema change.

## On hold / superseded

- **Remote-control command queue (SCRUM-373) is on hold, pending team sign-off,
  and is expected to be superseded.** The original design routed display-control
  commands through a MySQL `control_commands` queue that the BLE service would
  poll. The merged BLE integration replaces this with authenticated localhost
  REST: the web backend calls the BLE service directly and the command completes
  over BLE before the database is touched. Code review confirmed no executable
  code references a command queue, and no process polls the database for
  commands. The DB is not on the remote-control path. No `control_commands`
  table is built here. Final closure of SCRUM-373 waits on team/instructor
  acceptance of the deviation, which changes an approved requirement.

## Scope questions (not built here, pending confirmation)

The adapter interface requires `publish_connection_state` and
`publish_display_result`, which the service always calls but which may legally
no-op. Whether these must persist to this database (as connection-state or
display-result log tables) is a scope decision for the team, not settled by
code. No tables for them are included until confirmed. These are logging
concerns, distinct from the superseded command queue above.

## Not included here

Test seed data and verification scripts are kept local, not committed.

A reference concrete adapter now lives in this repo at
`backend/pc_client/mysql_adapter.py` (SCRUM-341/368), implementing
`ThermometerDatabaseAdapter` against this schema with `aiomysql`. It performs
the live-sample and missing-interval INSERTs; `upsert_history` is a
best-effort per-row insert (stretch scope, SCRUM-369); and
`reconcile_provisional_intervals`, `publish_connection_state`, and
`publish_display_result` are documented no-ops (see "Open items" and "Scope
questions" above). Credentials are never hardcoded: connection settings come
from `THERMOMETER_DB_HOST` / `_PORT` / `_USER` / `_PASSWORD` / `_NAME`
environment variables. See root README, "Database integration", and
`backend/pc_client/mock_run.py` for a hardware-free way to exercise it.
