# Requirements traceability

This matrix records the links verified during a read-only Jira review on
2026-09-07. Jira issues, comments, fields, and statuses were not modified.

Status meanings:

- **Implemented**: behavior exists in active code and has unit/build coverage.
- **Simulated**: logical behavior is implemented using fake sensors or the LED.
- **Interface only**: the integration contract compiles, but selected hardware
  and its acceptance timing are not implemented.
- **Acceptance pending**: code supports the requirement, but the end-to-end
  hardware/database/web timing test remains outstanding.

## System behavior enabled by this repository

| Requirement | Jira | Status | Repository contribution |
|---|---|---|---|
| SYS-HLR-500 | SCRUM-414 | Acceptance pending | Current sensor/status data is exposed to the database adapter and diagnostic REST API. |
| SYS-HLR-510 | SCRUM-415 | Acceptance pending | Per-sensor remote display control uses prioritized REST-to-BLE requests, ESP32-confirmed state, and the physical HD44780 LCD. |
| SYS-HLR-520 | SCRUM-416 | Acceptance pending | Autonomous discovery, power-cycle reconnect, first-current publication, and a ten-second recovery deadline are implemented. |

The web UI and concrete MySQL integration are implemented in this repository.
Final physical wiring, timing, and full-system acceptance still require the
assembled hardware.

## ESP32 firmware

| Requirement(s) | Jira issue(s) | Status | Implementation / verification |
|---|---|---|---|
| SWE-EMB-MLR-300..304 | SCRUM-456..460 | Implemented | ESP-IDF C application, continuous two-sensor state, independent history, and disconnect/recovery model; firmware builds. |
| SWE-EMB-MLR-305 | SCRUM-461 | Acceptance pending | Independent logical display flags are rendered on the physical two-row HD44780 LCD. |
| SWE-EMB-MLR-310..313 | SCRUM-466..469 | Implemented / acceptance pending | Celsius state, atomic snapshot, recovery, remote display state, and physical LCD presentation are implemented. |
| SWE-EMB-LLR-300..311 | SCRUM-470..481 | Implemented / acceptance pending | Ordered startup, independent DS18B20 acquisition on GPIO14/GPIO27, presence/CRC validation, 1 Hz snapshots, fixed 300-record rings, state mapping, faults, and recovery. |
| SWE-EMB-LLR-312..313 | SCRUM-482..483 | Implemented / acceptance pending | Active-low GPIO34/GPIO35 buttons use 40 ms debounce and the shared toggle path. |
| SWE-EMB-LLR-314..316 | SCRUM-484..486 | Implemented | Overflow-safe average calculation/validity and cached snapshot rendering. |
| SWE-EMB-LLR-317 | SCRUM-487 | Implemented / acceptance pending | Button and BLE state changes schedule immediate serialized LCD rendering; physical timing remains to be measured. |
| SWE-EMB-LLR-318..322 | SCRUM-488..492 | Implemented / acceptance pending | The 16x2 HD44780 parallel interface uses GPIO16/17/18/19/21/23; its directly powered backlight is not software-controllable. |
| SWE-EMB-LLR-323..326 | SCRUM-493..496 | Implemented | Canonical Celsius values, mutex-protected snapshots, boot identity, and recovery without restart. |
| SWE-EMB-LLR-327..328 | SCRUM-497..498 | Implemented | Local/remote commands share state mutation/rendering, and invalid commands do not change state. |

## BLE integration protocol

| Requirement(s) | Jira issue(s) | Status | Implementation / verification |
|---|---|---|---|
| INT-MLR-400..407 | SCRUM-499..506 | Implemented | BLE transport, requester-only protocol, current/display/history transactions, recovery, access control, versioning, and errors. |
| INT-LLR-400..406 | SCRUM-507..513 | Implemented | Custom service discovery, no notifications, request IDs/header, GET_CURRENT, and validated SET_DISPLAY response. |
| INT-LLR-407..410 | SCRUM-514..517 | Implemented | Metadata-first, sequence-addressed, complete-record, MTU-safe chunked history. |
| INT-LLR-411..415 | SCRUM-518..522 | Implemented | MTU adaptation, status/version rejection, authenticated bonding, and automatic reconnect discovery. |
| INT-LLR-416 | SCRUM-646 | Acceptance pending | Display priority and a post-timeout device-state confirmation prevent false errors; the five-second acknowledgement guard does not replace the one-second physical-actuation acceptance measurement. |

Protocol layout, opcodes, statuses, UUIDs, and timing are defined once in
`protocol/thermometer_protocol.json`. Python loads it directly; firmware CMake
generates `firmware/build/generated/thermometer_config.h` from it.

## Python BLE connector

| Requirement(s) | Jira issue(s) | Status | Implementation / verification |
|---|---|---|---|
| SWE-CONN-MLR-500..506 | SCRUM-523..529 | Implemented | Separate service process, 1 Hz polling, missing intervals, history recovery, REST control IPC, and automatic reconnect. |
| SWE-CONN-MLR-507..508 | SCRUM-642..643 | Acceptance pending | Startup/history and power-on recovery deadlines are represented; production database and hardware timing remain. |
| SWE-CONN-LLR-500..509 | SCRUM-535..544 | Implemented | Executable worker, monotonic polling, persistence records, reconnects, metadata/chunks/retries, reconstructed timestamps, and duplicate-safe history batches. |
| SWE-CONN-LLR-513..514 | SCRUM-548..549 | Implemented | Revisioned connection-state publication and per-cycle BLE/database failure isolation. |
| SWE-CONN-LLR-515..516 | SCRUM-644..645 | Acceptance pending | Ten-second synchronization/recovery budgets and partial results are implemented; final external persistence timing remains. |

Unit coverage is under `backend/pc_client/tests`; `master_test.py` discovers the
complete active suite. Firmware compilation and hardware acceptance are
separate integration checks.

## Intentional product deviation

SWE-CONN-LLR-510..512 (SCRUM-545..547) specify a MySQL
`control_commands` polling/claiming/completion queue. This integration instead
uses authenticated localhost REST control between the web backend and the BLE
service. Confirmed display results are still passed to the database adapter,
but the MySQL queue requirements are **not implemented** and are not claimed by
this repository.

## Database subsystem

| Requirement(s) | Jira issue(s) | Status | Implementation / verification |
|---|---|---|---|
| SWE-DB-MLR-551 | SCRUM-531 | Implemented | temperature_samples persists both probe series, computed average, and per-series status with sample identity (boot_id, sample_seq). Status vocabulary follows the implementation (VALID/DISCONNECTED/NOT_RETRIEVED/MISSING); requirement text update is a docs task. |
| SWE-DB-MLR-552 | SCRUM-532 | Implemented | users, alert_recipients, alert_rules, and alert_rule_recipients junction persist user roles, alert recipients, and alert rules for the web application. |
| SWE-DB-LLR-550 | SCRUM-550 | Implemented | temperature_samples created with all specified fields except device_id, intentionally omitted: single-device system by design, adapter keys on BLE address/name, so the column would hold no distinguishing value. Closed deviation. Also carries a nullable failure_reason (SCRUM-341), populated for PROVISIONAL rows explaining a missed poll; not yet its own requirement. |
| SWE-DB-LLR-551 | SCRUM-551 | Implemented (see note) | UNIQUE KEY (boot_id, sample_seq) enforces real-sample uniqueness (natural key demoted from PK so NULL-keyed PROVISIONAL rows insert under a surrogate id). Duplicate rejection covered by an automated test and a live manual test against a real server (backend/pc_client/tests/test_mysql_adapter.py, SCRUM-341): error 1062 is caught and reported, not raised or silently ignored. Note: the key is not device-scoped, i.e. not UNIQUE(device_id, boot_id, sample_seq) as SCRUM-341's own write-contract draft assumed - device_id was deliberately descoped from the schema (see SWE-DB-LLR-550's closed deviation: single-device system, no multi-device basis in spec). Uniqueness here is therefore global rather than per-device; equivalent for one device, and would need revisiting if the system ever supported more than one. |
| SWE-DB-LLR-552 | SCRUM-552 | Implemented | Index entry_index (observed_at_utc) verified live with EXPLAIN against a real server for both required query forms: latest-sample (`ORDER BY observed_at_utc DESC LIMIT 1`) uses an index scan (reverse) at any table size; time-window range (`WHERE observed_at_utc BETWEEN ...`) requires a realistic row count to confirm - MySQL's optimizer correctly prefers a table scan over the index on a near-empty table, which is expected behavior, not a defect. Verified against 20k synthetic rows with a narrow (60s) window: index range scan on entry_index, as intended. Synthetic rows removed after verification. |
| SWE-DB-LLR-554 | SCRUM-554 | Implemented | users table: unique username, password_hash (no plaintext), role ENUM(USER,ADMIN), enabled (default TRUE), created/updated UTC audit timestamps. Verified: role storage, enabled default, updated_at auto-refresh on edit, username uniqueness rejection (error 1062). |
| SWE-DB-LLR-555 | SCRUM-555 | Implemented | alert_recipients table: type ENUM(EMAIL,SMS), address, no per-type uniqueness. Verified: multiple EMAIL and SMS recipients persist and are retrievable. |
| SWE-DB-LLR-556 | SCRUM-556 | Implemented | alert_rules (min/max thresholds DECIMAL(5,2) Celsius, high/low messages, monitored_series) plus alert_rule_recipients many-to-many junction. Verified: all five rule fields persist; rule links to multiple recipients; ON DELETE CASCADE removes links but not recipients. |
| SWE-DB-LLR-559 | SCRUM-559 | Implemented | Temperature and threshold fields typed DECIMAL(5,2), stored in Celsius. |
| SWE-DB-LLR-560 | SCRUM-560 | Implemented | Timestamps stored UTC. Server timezone set to UTC (default-time-zone='+00:00'); verified @@global.time_zone = +00:00 and a DB-stamped row returns UTC. |

See [backend/database/README.md](../backend/database/README.md) for schema design decisions and open flags.
