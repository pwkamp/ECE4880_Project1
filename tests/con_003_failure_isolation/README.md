<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# CON-003: Missing one-second intervals and BLE/database failure isolation

Primary type: Fault-injection integration  
Execution mode: Automated  
Current feasibility: Runnable with adapter spy; MySQL confirmation pending  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-CONN-MLR-504 | [SCRUM-527](https://pkamp.atlassian.net/browse/SCRUM-527) | SWE-CONN-MLR-504 - Unavailable-Data Recording |
| SWE-CONN-LLR-503 | [SCRUM-538](https://pkamp.atlassian.net/browse/SCRUM-538) | SWE-CONN-LLR-503 - Missing Poll Persistence |
| SWE-CONN-LLR-514 | [SCRUM-549](https://pkamp.atlassian.net/browse/SCRUM-549) | SWE-CONN-LLR-514 - Polling Failure Isolation |

## Purpose and usefulness

Fault injection proves continuity and data semantics under the failures the system will actually encounter, not just that exceptions are caught.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, scripted-ble, implementation:CON-003:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use fake clock, scripted BLE failures/timeouts, an adapter that can fail selected writes, and isolated MySQL when available.

## Detailed repeatable procedure

1) Establish a valid value. 2) Fail three consecutive scheduled polls. 3) Verify one distinct provisional record per boundary with null values and no carried-forward number. 4) Restore BLE and confirm valid records resume. 5) Make one current write and one provisional write raise exceptions. 6) Fill the persistence queue to its 300-item capacity. 7) Verify errors/overflow are observable and the polling/state loop remains alive. 8) Confirm later cycles continue.

## PASS criteria

Each missed boundary is represented exactly once and distinctly from valid data; prior numeric values are never copied forward; BLE or database failures affect only their cycles; queue overflow is reported; and the connector continues polling unless an explicitly controlled fatal condition occurs.

## Independent criteria source

One-second provisional behavior and nontermination are explicit. Queue capacity 300 is from released config and is tested as an implementation limit.

## Test type and automation rationale

All boundaries can be simulated deterministically, so this belongs in automated integration tests.

## Required instrumentation and observability

Add configurable failing MySQL adapter, fake clocks, queue metrics, correlation IDs, and assertions that unavailable API responses omit stale numbers.

## Evidence retained

Boundary records, exception/overflow metrics, process liveness log, recovery rows.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
