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
| SYS-HLR-510 | SCRUM-415 | Simulated | Per-sensor remote display control uses prioritized REST-to-BLE requests and ESP32-confirmed state; the LED simulates the LCD. |
| SYS-HLR-520 | SCRUM-416 | Acceptance pending | Autonomous discovery, power-cycle reconnect, first-current publication, and a ten-second recovery deadline are implemented. |

The internet-facing web UI, concrete MySQL implementation, alerts, and final
hardware are separate workstreams, so this repository alone cannot close the
system-level requirements.

## ESP32 firmware

| Requirement(s) | Jira issue(s) | Status | Implementation / verification |
|---|---|---|---|
| SWE-EMB-MLR-300..304 | SCRUM-456..460 | Implemented | ESP-IDF C application, continuous two-sensor state, independent history, and disconnect/recovery model; firmware builds. |
| SWE-EMB-MLR-305 | SCRUM-461 | Simulated | Independent logical display flags rendered through the LED simulator. |
| SWE-EMB-MLR-310..313 | SCRUM-466..469 | Implemented / interface only | Celsius state, atomic snapshot, recovery, and remote display state are implemented; physical LCD presentation is an interface stub. |
| SWE-EMB-LLR-300..311 | SCRUM-470..481 | Implemented / simulated | Ordered startup, per-sensor runtime records, independent fake acquisition, 1 Hz snapshots, fixed 300-record rings, state mapping, faults, and recovery. Real sensor drivers remain pending. |
| SWE-EMB-LLR-312..313 | SCRUM-482..483 | Interface only | Local button API and shared toggle path exist; GPIO/debounce hardware is not selected. |
| SWE-EMB-LLR-314..316 | SCRUM-484..486 | Implemented | Overflow-safe average calculation/validity and cached snapshot rendering. |
| SWE-EMB-LLR-317 | SCRUM-487 | Interface only | Immediate render scheduling contract exists; physical input timing is not yet verified. |
| SWE-EMB-LLR-318..322 | SCRUM-488..492 | Interface only | Real LCD/backlight integration contract compiles; no display bus, geometry, or input hardware is selected. |
| SWE-EMB-LLR-323..326 | SCRUM-493..496 | Implemented | Canonical Celsius values, mutex-protected snapshots, boot identity, and recovery without restart. |
| SWE-EMB-LLR-327..328 | SCRUM-497..498 | Implemented | Local/remote commands share state mutation/rendering, and invalid commands do not change state. |

## BLE integration protocol

| Requirement(s) | Jira issue(s) | Status | Implementation / verification |
|---|---|---|---|
| INT-MLR-400..407 | SCRUM-499..506 | Implemented | BLE transport, requester-only protocol, current/display/history transactions, recovery, access control, versioning, and errors. |
| INT-LLR-400..406 | SCRUM-507..513 | Implemented | Custom service discovery, no notifications, request IDs/header, GET_CURRENT, and validated SET_DISPLAY response. |
| INT-LLR-407..410 | SCRUM-514..517 | Implemented | Metadata-first, sequence-addressed, complete-record, MTU-safe chunked history. |
| INT-LLR-411..415 | SCRUM-518..522 | Implemented | MTU adaptation, status/version rejection, authenticated bonding, and automatic reconnect discovery. |
| INT-LLR-416 | SCRUM-646 | Acceptance pending | A 0.9 s connector timeout and display priority are enforced; final physical-LCD end-to-end measurement remains. |

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
| SWE-DB-MLR-551 | SCRUM-531 | Implemented | temperature_samples persists probe1, probe2, and computed-average series with per-series value + status and sample identity (boot_id, sample_seq). Note: implementation status vocabulary (VALID/DISCONNECTED/NOT_RETRIEVED/MISSING) differs from this requirement's text (unplugged-sensor/no-data/provisional/derived-unavailable); reconciliation flagged for team. |
| SWE-DB-LLR-550 | SCRUM-550 | Implemented | temperature_samples created with all specified fields except device_id, which is intentionally omitted: single-device system per spec, and the adapter identifies the device by BLE address/name, not a stored id. Deviation flagged for review. |
| SWE-DB-LLR-551 | SCRUM-551 | Acceptance pending | UNIQUE KEY (boot_id, sample_seq) enforces real-sample uniqueness (natural key demoted from PK to allow NULL-keyed PROVISIONAL rows under a surrogate id). Duplicate-rejection verified manually (error 1062); reproducible verification not yet committed. |
| SWE-DB-LLR-552 | SCRUM-552 | Acceptance pending | Index entry_index (observed_at_utc) created (device_id dropped, so keyed on time alone). EXPLAIN verification incomplete on the required query forms. |
| SWE-DB-LLR-559 | SCRUM-559 | Implemented | Temperature fields (sensor1_c, sensor2_c, average_c) typed DECIMAL(5,2), stored in Celsius, matching the i16 centi-Celsius wire format. |
| SWE-DB-LLR-560 | SCRUM-560 | Acceptance pending | observed_at_utc typed DATETIME. UTC compliance requires the MySQL server timezone set to UTC; server currently runs local time, so DB-generated defaults are not yet UTC. |

See [backend/database/README.md](../backend/database/README.md) for schema design decisions and open flags.