# Database Module

MySQL storage for the temperature monitoring system. Owns the `thermometer`
database and the `temperature_samples` table (SCRUM-371).

## Build

Run against a local MySQL server:

```
mysql -u root -p < schema.sql
```

`schema.sql` is re-runnable. It drops and recreates the `thermometer` database,
so it wipes existing data on every run.

## Schema

`temperature_samples` stores one row per 1 Hz poll (wide grain: both probes and
the computed average as columns on the same row). Rows arrive from the BLE
connection service through the database adapter (see root README, "Database
integration").

Traceability:

| Piece | Requirement |
|---|---|
| Column set | SWE-DB-LLR-550 |
| Uniqueness of a real sample | SWE-DB-LLR-551 |
| Time-window / latest-sample index | SWE-DB-LLR-552 |
| Celsius storage | SWE-DB-LLR-559 |
| UTC timestamps | SWE-DB-LLR-560 |
| Series + status model | SWE-DB-MLR-551 |

Status values (per sensor): `VALID`, `DISCONNECTED`, `NOT_RETRIEVED`, `MISSING`.
Record source: `LIVE`, `HISTORY`, `PROVISIONAL`. These strings match the
connection service's implementation verbatim; seed rows are tagged `PROVISIONAL` like any
other synthetic/non-live row, distinguishable from real data by the absence of
a matching `boot_id`/`sample_seq` pair rather than by a separate source value.


## Key design decisions

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
  when the reading is not trustworthy. The adapter delivers them already NULL
  (no sentinel values). Status columns are NOT NULL: a reading always has a
  state.
- **`average_c` is NULL unless both probes are valid.** The service computes the
  average only when both sensor readings are valid; a single valid probe yields
  NULL, not a one-probe average. `average_valid` reflects this.
- **`DECIMAL(5,2)` Celsius.** Matches the `i16` centi-Celsius wire format at
  correct resolution, sized to the sensor's physical range.
- **`DATETIME`, not `TIMESTAMP`.** Stores the value with no timezone conversion;
  UTC correctness is a property of what's bound into the column at insert time,
  not of the column type (see Timestamp handling).
- **No `device_id`.** SWE-DB-LLR-550 names a `device_id` field, but the system is
  single-device per spec, and the adapter identifies the device by BLE address
  and advertised name rather than a stored id. A `device_id` column would hold no
  distinguishing information, so it is omitted. Deviation flagged for review.

## Timestamp handling

- `observed_at_utc` is supplied explicitly by the connection service on every
  insert (`SampleRecord.observed_at_utc` is a required, non-optional field in
  the adapter contract) — it is computed in Python before the adapter is ever
  called, not left to MySQL. The schema's `DEFAULT CURRENT_TIMESTAMP` is a
  fallback for the column, not the live data path; it should not fire under
  normal operation.
- The root README states connector timestamps are timezone-aware UTC at the
  point they're computed. If the adapter binds `observed_at_utc` as an
  explicit parameter (expected, given the field is required), `DATETIME`
  stores that literal value regardless of MySQL server timezone — server
  timezone only affects `DEFAULT`/`NOW()` evaluation, not bound parameters.
  **Not yet confirmed against the actual adapter implementation** (it lives
  outside this repo) — verify before treating server-timezone configuration
  as the blocker for SWE-DB-LLR-560.
- `HISTORY` rows are backfilled: their timestamps are reconstructed by the
  service from a live anchor and the 1 Hz sample period, so they are
  PC-clock-derived, not device-observed.


## Open items

- Server timezone dependency for SWE-DB-LLR-560 is unconfirmed, not settled.
  If the adapter always binds `observed_at_utc` explicitly (implied by it being
  a required, non-optional field on `SampleRecord`), server timezone is
  irrelevant and no config change is needed. If any path instead relies on
  `DEFAULT CURRENT_TIMESTAMP`, server timezone matters and must be set to UTC
  (`default-time-zone='+00:00'` in `my.ini`). Confirm which is true against the
  actual adapter implementation before doing, or skipping that change.
- Provisional rows are not write-once. The adapter method
  `reconcile_provisional_intervals` implies previously-stored `PROVISIONAL` rows
  may be updated to a final state after a history sync. Update semantics are
  owned by the adapter implementation (not in this repo); status and
  `average_valid` columns are therefore mutable by design.
- Status/source vocabulary matches the implementation, not the approved
  requirement text. SWE-DB-MLR-551 names statuses `unplugged-sensor / no-data /
  provisional / derived-unavailable`; the implementation uses `VALID /
  DISCONNECTED / NOT_RETRIEVED / MISSING`. The requirement text and the code
  disagree and should be reconciled by the team.

## Scope questions (not built here, pending confirmation)

The adapter interface requires `publish_connection_state` and
`publish_display_result`, which the service always calls. Whether these must
persist to this database (as connection-state / display-result tables) or may
legitimately no-op is a scope decision for the team/Jira, not settled by code.
No tables for them are included until confirmed.

## Not included here

Test seed data is kept local, not committed. The concrete database adapter and
credentials live outside the repo (see root README, "Database integration").
