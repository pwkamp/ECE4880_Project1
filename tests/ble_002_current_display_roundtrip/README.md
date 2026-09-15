<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# BLE-002: GET_CURRENT and SET_DISPLAY protocol round trips

Primary type: BLE HIL protocol integration  
Execution mode: Semi-automated  
Current feasibility: Partially runnable; LED simulates LCD  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| INT-MLR-402 | [SCRUM-501](https://pkamp.atlassian.net/browse/SCRUM-501) | INT-MLR-402 - Current Data Transaction |
| INT-MLR-403 | [SCRUM-502](https://pkamp.atlassian.net/browse/SCRUM-502) | INT-MLR-403 - Remote Display Control Transaction |
| INT-LLR-404 | [SCRUM-511](https://pkamp.atlassian.net/browse/SCRUM-511) | INT-LLR-404 - GET_CURRENT Opcode |
| INT-LLR-405 | [SCRUM-512](https://pkamp.atlassian.net/browse/SCRUM-512) | INT-LLR-405 - SET_DISPLAY Opcode |
| INT-LLR-406 | [SCRUM-513](https://pkamp.atlassian.net/browse/SCRUM-513) | INT-LLR-406 - SET_DISPLAY Response |

## Purpose and usefulness

Round-trip comparison proves the wire contract, state mutation, and presentation agree; encoder-only tests would miss integration mismatches.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, ble, verification-firmware, implementation:BLE-002:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use scripted central, authenticated bond, known firmware sensor states, and observable local display state.

## Detailed repeatable procedure

1) Issue GET_CURRENT and decode boot ID, newest sequence, both temperatures/statuses/display flags, and average. 2) Compare with an atomic firmware snapshot. 3) Issue SET_DISPLAY ON/OFF for each sensor. 4) Verify response success, sensor ID, enabled flag, and visible state. 5) Repeat while a sensor is disconnected. 6) Inject an invalid sensor/value and inspect response/no-state-change. 7) Confirm physical/simulated display matches.

## PASS criteria

GET_CURRENT fields exactly match one firmware snapshot. Valid SET_DISPLAY changes only the requested state and returns the resulting externally visible state; disconnected and invalid cases return defined status and never present invalid temperature data or corrupt state.

## Independent criteria source

Field layout and status values come from protocol version 2; comparison is exact except temperatures retain the specified centi-Celsius representation.

## Test type and automation rationale

Scripts can assert payloads and responses, while physical display confirmation keeps the release variant HIL.

## Required instrumentation and observability

Add firmware snapshot test endpoint in diagnostic builds, BLE transaction recorder, and physical display observer.

## Evidence retained

Raw packets, decoded JSON, firmware snapshot, display capture, state before/after.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
