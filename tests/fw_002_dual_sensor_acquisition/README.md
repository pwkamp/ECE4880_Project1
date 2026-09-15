<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-002: Continuous dual-sensor acquisition and fault isolation

Primary type: Firmware unit plus HIL  
Execution mode: Semi-automated  
Current feasibility: Partially runnable with fake sensors  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-301 | [SCRUM-457](https://pkamp.atlassian.net/browse/SCRUM-457) | SWE-EMB-MLR-301 - Continuous Sensor Acquisition |
| SWE-EMB-LLR-301 | [SCRUM-471](https://pkamp.atlassian.net/browse/SCRUM-471) | SWE-EMB-LLR-301 - Per-Sensor Runtime Record |
| SWE-EMB-LLR-302 | [SCRUM-472](https://pkamp.atlassian.net/browse/SCRUM-472) | SWE-EMB-LLR-302 - Continuous Acquisition Loop |
| SWE-EMB-LLR-303 | [SCRUM-473](https://pkamp.atlassian.net/browse/SCRUM-473) | SWE-EMB-LLR-303 - Independent Sensor Reads |

## Purpose and usefulness

Table-driven independent faults exercise the concurrency risk the requirements target, not merely successful reads.

## Profiles and qualification credit

- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, verification-firmware, implementation:FW-002:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use injectable sensor backends with independent scripted value/success sequences and a real-sensor HIL variant.

## Detailed repeatable procedure

1) Start both acquisition tasks. 2) Feed valid independent sequences and verify each runtime record updates only after validation. 3) Delay Sensor 1 reads while Sensor 2 continues. 4) Force Sensor 1 failures while Sensor 2 returns valid values; then reverse. 5) Run at least 60 sample cycles. 6) Inspect temperature, validity, display flag, and sequence fields after every event.

## PASS criteria

Each sensor has its own complete runtime record; a new read begins after the prior cycle; invalid results never replace a valid numeric value as valid; and a failure or delay on one sensor never skips or blocks updates from the other.

## Independent criteria source

Pass conditions are direct state invariants. Sixty cycles cover the current fake-disconnect cycle and repeated scheduling without claiming endurance.

## Test type and automation rationale

Most cases belong in an automated firmware unit harness; the real-bus independence check remains HIL.

## Required instrumentation and observability

Add injectable sensor interfaces, deterministic scheduler/test clock, per-task event trace, and on-target Unity tests.

## Evidence retained

Unit results, event trace, HIL bus log, runtime-record snapshots.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
