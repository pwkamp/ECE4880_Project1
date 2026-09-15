<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-003: One-second 300-record circular history

Primary type: Firmware unit test  
Execution mode: Automated  
Current feasibility: Logic present; dedicated C unit harness missing  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-302 | [SCRUM-458](https://pkamp.atlassian.net/browse/SCRUM-458) | SWE-EMB-MLR-302 - Two 300-Reading History Buffers |
| SWE-EMB-LLR-304 | [SCRUM-474](https://pkamp.atlassian.net/browse/SCRUM-474) | SWE-EMB-LLR-304 - One-Second History Timer |
| SWE-EMB-LLR-305 | [SCRUM-475](https://pkamp.atlassian.net/browse/SCRUM-475) | SWE-EMB-LLR-305 - Fixed-Size Circular Buffers |
| SWE-EMB-LLR-306 | [SCRUM-476](https://pkamp.atlassian.net/browse/SCRUM-476) | SWE-EMB-LLR-306 - History Record Contents |
| SWE-EMB-LLR-307 | [SCRUM-477](https://pkamp.atlassian.net/browse/SCRUM-477) | SWE-EMB-LLR-307 - History Ordering |

## Purpose and usefulness

Boundary and multi-wrap cases directly target circular-buffer errors and cover both sensors with one parameterized test.

## Profiles and qualification credit

- unit: automated; FULL evidence; capabilities: python, pytest, jsonschema, firmware-unity, implementation:FW-003:unit.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use a deterministic 1000 ms test clock and independent history buffers for both sensors.

## Detailed repeatable procedure

1) Append known valid and disconnected records for sequences 1 through 300 at exact one-second ticks. 2) Verify counts, fields, and oldest-to-newest retrieval. 3) Append sequence 301 and confirm only sequence 1 is overwritten. 4) Continue through at least sequence 650 to test multiple wraps. 5) Retrieve arbitrary ranges crossing the wrap point for each sensor. 6) Inject one delayed tick and verify the timer policy is visible rather than silently duplicating data.

## PASS criteria

Exactly one record per sensor is produced per 1000 ms boundary; capacity never exceeds 300; record 301 overwrites the oldest only; all records preserve sequence/value/status; and every retrieval is chronological regardless of wrap.

## Independent criteria source

Capacity 300 and period 1000 ms are exact Jira/shared-config values; sequences are compared exactly.

## Test type and automation rationale

Deterministic data-structure and timer behavior is ideal for automated unit testing without physical hardware.

## Required instrumentation and observability

Add host/on-target Unity tests, fake clock, direct buffer inspection API, and dual-sensor parameterization.

## Evidence retained

Test vectors, unit log, retrieved sequences, timing-event trace.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
