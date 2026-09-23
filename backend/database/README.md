# Database Module

MySQL storage for the temperature monitoring system. Owns the `thermometer`
database and its tables: `temperature_samples` plus email-alert configuration.

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
| `alert_recipients` | Enabled email destinations | SWE-DB-LLR-555 |
| `alert_settings` | Single-row (`id=1`) master enable/disable toggle for all alerting | (none) |
| `alert_rules` | Threshold rules with messages and monitored series | SWE-DB-LLR-556 |
| `alert_rule_recipients` | Junction linking rules to recipients (many-to-many) | SWE-DB-LLR-556 |

Rows in `temperature_samples` arrive from the BLE connection service through the
database adapter. The frontend Node service reads/writes the alert tables through
the local `/api/alert-config` endpoint.

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
| History and email-alert configuration storage | SWE-DB-MLR-552 |
| deliberate absence of application-user tables | SWE-DB-LLR-554 |
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

### Email alerts and trusted-local operation

- **Surrogate primary key on every table**, mirroring `temperature_samples`.
- **No application accounts.** The stakeholder-approved trusted-local design
  has no `users` table, passwords, login, or USER/ADMIN roles.
- **Email only.** `alert_recipients.type` accepts only `EMAIL`; SMS/phone
  delivery and validation are out of scope. Multiple email rows are supported.
- **`enabled` defaults TRUE.** New email recipients and rules are active.
- **`alert_settings` is a single-row master toggle.** `id` is constrained to `1`
  (`CHECK (id = 1)`); its `enabled` column gates alerting globally, independent
  of the per-recipient and per-rule `enabled` flags. `frontend/server/alertConfig.ts`
  creates this table if missing, seeds row `id=1`, and reads/writes it alongside
  the recipient and rule tables through the same `/api/alert-config` endpoint.
- **Rule/recipient link is many-to-many.** A rule can notify several recipients
  and a recipient can serve several rules, so the link is a junction table
  (`alert_rule_recipients`) rather than a column. Both foreign keys are
  `ON DELETE CASCADE`: deleting a rule or a recipient removes its links but not
  the other party.
- **Thresholds are `DECIMAL(5,2)` Celsius**, matching `temperature_samples`. Both
  `min_threshold` and `max_threshold` are required (every rule is a bounded band
  with a message for each side).
- **`monitored_series` is `ENUM('SENSOR1','SENSOR2')`.** The UI applies its
  shared threshold configuration to both physical sensors, so persistence
  writes one rule row for each source. Average-based alerts were removed from
  the application model during the Lab 1 cleanup.

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
- `created_at_utc` / `updated_at_utc` on the alert tables use
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
- Provisional rows are not write-once (implemented, SCRUM-369). A `PROVISIONAL`
  row has NULL `boot_id`/`sample_seq`, so it can't be matched to a recovered
  `HISTORY` sample via the natural key. The reference adapter
  (`backend/pc_client/mysql_adapter.py::reconcile_provisional_intervals`)
  instead deletes a `PROVISIONAL` row when a `HISTORY` sample from the same
  batch lands within half a sample period of its `observed_at_utc` - that
  `HISTORY` row (already written by `upsert_history`, which the persistence
  worker always runs first) is strictly better data for the same real-world
  second. Verified live: a real recovered sample correctly removes the
  placeholder it supersedes, and an unrelated `PROVISIONAL` row outside the
  match window is left alone.
- Status/source vocabulary follows the implementation (decided). The schema uses
  the code's values (`VALID / DISCONNECTED / NOT_RETRIEVED / MISSING`) so the
  database and BLE service agree exactly. The approved requirement text
  (SWE-DB-MLR-551) still lists the older `unplugged-sensor / no-data / provisional
  / derived-unavailable` terms; updating that text to match the implementation is
  a requirements-doc task, not a schema change.

## Superseded baseline

- **Application user accounts remain removed.** The trusted-local deployment
  has no `users` table, passwords, session cookie, login, or USER/ADMIN roles.
  The later qualification work added a real `/api/alert-config` consumer for
  the email-only recipient and rule tables, so those tables are no longer
  dead schema. SMS and average-source alert configuration remain removed.

- **Remote-control command queue is superseded by stakeholder decision.** The original design routed display-control
  commands through a MySQL `control_commands` queue that the BLE service would
  poll. The merged BLE integration replaces this with authenticated localhost
  REST: the web backend calls the BLE service directly and the command completes
  over BLE before the database is touched. Code review confirmed no executable
  code references a command queue, and no process polls the database for
  commands. The DB is not on the remote-control path. No `control_commands`
  table is built here. The affected Jira descriptions and dated baseline-change
  comments record this decision.

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
`backend/pc_client/mysql_adapter.py` (SCRUM-341/368/369), implementing
`ThermometerDatabaseAdapter` against this schema with `aiomysql`. It performs
the live-sample and missing-interval INSERTs; `upsert_history` (per-row
insert, tolerant of re-synced overlap) and `reconcile_provisional_intervals`
(deletes superseded `PROVISIONAL` placeholders, see "Open items" above) are
both implemented and verified live. `publish_connection_state` and
`publish_display_result` remain documented no-ops (see "Scope questions"
above - no destination tables exist yet). Credentials are never hardcoded:
connection settings come from `THERMOMETER_DB_HOST` / `_PORT` / `_USER` /
`_PASSWORD` / `_NAME` environment variables.

**Requires a running MySQL server** - this is a client only, it does not
start or embed one. Install MySQL locally (or point the env vars above at a
shared instance), then apply `schema.sql` once before running anything else
in this section.

See root README, "Database integration", and `backend/pc_client/mock_run.py`
for a hardware-free way to exercise it (including a simulated dropped-poll
mode, `--drop-after`/`--drop-for`, to exercise the missing-interval path).
