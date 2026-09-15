<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-008: Atomic current snapshot and boot/session identity

Primary type: Firmware concurrency unit test  
Execution mode: Automated  
Current feasibility: Logic present; C test harness missing  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-311 | [SCRUM-467](https://pkamp.atlassian.net/browse/SCRUM-467) | SWE-EMB-MLR-311 - Atomic Current Snapshot |
| SWE-EMB-LLR-324 | [SCRUM-494](https://pkamp.atlassian.net/browse/SCRUM-494) | SWE-EMB-LLR-324 - Snapshot Locking |
| SWE-EMB-LLR-325 | [SCRUM-495](https://pkamp.atlassian.net/browse/SCRUM-495) | SWE-EMB-LLR-325 - Boot Identifier |

## Purpose and usefulness

The stress test targets torn reads and cross-boot ambiguity, the failure modes the synchronization and boot ID requirements exist to prevent.

## Profiles and qualification credit

- unit: automated; FULL evidence; capabilities: python, pytest, jsonschema, firmware-unity, implementation:FW-008:unit.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use concurrent scripted writers for both sensor runtime records, snapshot reader, deterministic barriers, and controllable restart.

## Detailed repeatable procedure

1) Repeatedly update Sensor 1 and Sensor 2 around synchronization barriers while reading current snapshots. 2) Tag every update generation. 3) Assert each snapshot contains a self-consistent pair of values, states, display flags, average, and sequence identity. 4) Run at least 10,000 interleavings under a stress scheduler. 5) Restart firmware and compare boot/session IDs and sequence interpretation. 6) Verify current and history metadata carry the boot ID.

## PASS criteria

No snapshot mixes fields from incompatible protected update instants; average validity/value matches the copied records; all identity fields are present; and a restart produces a distinguishable boot/session identity used by both current and history metadata.

## Independent criteria source

Field consistency is exact. Ten thousand interleavings is a pragmatic race screen, not a reliability claim; boot IDs must differ or otherwise be monotonically distinguishable by the released design.

## Test type and automation rationale

Deterministic barriers plus stress repetition are best automated at unit level.

## Required instrumentation and observability

Add concurrency test hooks/barriers, snapshot generation tags in test builds, restart fixture, and Unity/host stress runner.

## Evidence retained

Interleaving seed, unit log, any minimal failing schedule, boot/current/history captures.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
