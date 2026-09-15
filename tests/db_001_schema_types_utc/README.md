<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# DB-001: Temperature schema, types, statuses, device identity, and UTC

Primary type: MySQL schema integration  
Execution mode: Automated  
Current feasibility: Partially runnable; current schema deviates and migration is destructive  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-DB-MLR-550 | [SCRUM-530](https://pkamp.atlassian.net/browse/SCRUM-530) | SWE-DB-MLR-550 - MySQL Persistent Storage |
| SWE-DB-MLR-551 | [SCRUM-531](https://pkamp.atlassian.net/browse/SCRUM-531) | SWE-DB-MLR-551 - Temperature Sample Schema |
| SWE-DB-MLR-554 | [SCRUM-534](https://pkamp.atlassian.net/browse/SCRUM-534) | SWE-DB-MLR-554 - Canonical Time and Units |
| SWE-DB-LLR-550 | [SCRUM-550](https://pkamp.atlassian.net/browse/SCRUM-550) | SWE-DB-LLR-550 - temperature_samples Table |
| SWE-DB-LLR-559 | [SCRUM-559](https://pkamp.atlassian.net/browse/SCRUM-559) | SWE-DB-LLR-559 - Celsius Storage |
| SWE-DB-LLR-560 | [SCRUM-560](https://pkamp.atlassian.net/browse/SCRUM-560) | SWE-DB-LLR-560 - UTC Timestamp Storage |

## Purpose and usefulness

information_schema plus boundary inserts verifies what MySQL enforces, not just what schema.sql appears to declare.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, mysql-test-instance, production-mysql-adapter, implementation:DB-001:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use ephemeral MySQL configured for UTC and a non-destructive migration runner. Load approved status vocabulary and device-identity decision.

## Detailed repeatable procedure

1) Apply migrations to empty and already-populated databases. 2) Inspect information_schema for temperature_samples columns, nullability, types, keys, and enums/checks. 3) Insert boundary values -10.00 and +63.00 C and representative status combinations. 4) Insert explicit timezone-aware UTC timestamps and exercise any database defaults. 5) Read through the production adapter. 6) Attempt out-of-range/invalid-status rows. 7) Re-run migrations and verify existing data remains.

## PASS criteria

Schema includes every approved field, including device_id unless a linked deviation removes it; stores both probes and same-sample average/status/session/sample identity; DECIMAL precision preserves 0.01 C across the range; all timestamps/defaults are UTC; invalid values/statuses are rejected; and migrations are repeatable without data loss.

## Independent criteria source

Columns/range/UTC come from Jira. Current device_id and status-vocabulary deviations must be approved before PASS; DECIMAL(5,2) is adequate for the required range and centi-degree wire data.

## Test type and automation rationale

An ephemeral database makes schema and migration checks deterministic and safe for automated CI.

## Required instrumentation and observability

Replace DROP DATABASE script with migrations; add device_id or approved deviation; reconcile statuses; implement adapter; force UTC session/server and schema contract tests.

## Evidence retained

Migration logs, information_schema snapshot, boundary rows, adapter round trip, invalid-insert results.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
