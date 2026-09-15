<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# BLE-006: Automatic BLE link-loss recovery

Primary type: BLE HIL recovery  
Execution mode: Semi-automated  
Current feasibility: Partially runnable with current service and fake firmware backends  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| INT-MLR-405 | [SCRUM-504](https://pkamp.atlassian.net/browse/SCRUM-504) | INT-MLR-405 - Connection Recovery |
| INT-LLR-415 | [SCRUM-522](https://pkamp.atlassian.net/browse/SCRUM-522) | INT-LLR-415 - Reconnect Discovery |

## Purpose and usefulness

Real link loss exercises OS Bluetooth, callbacks, stale handles, and reconnection sequencing that mocked exchanges cannot fully represent.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, ble, verification-firmware, implementation:BLE-006:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Run the connector and third box with an authenticated registered target; use RF blocking, power relay, or forced disconnect while logging state.

## Detailed repeatable procedure

1) Establish steady 1 Hz polling. 2) Force link loss without stopping the application. 3) Confirm disconnection callback changes state and automatic scanning begins. 4) Restore the same device and verify fresh discovery/connection/auth/verification. 5) Repeat with a restarted device/boot ID and stale Windows device handle. 6) Confirm polling and history recovery resume without user restart. 7) Verify an explicit user disconnect suppresses retries.

## PASS criteria

Unexpected loss automatically enters recovery and resumes valid polling/history with the correct target and boot identity; stale callbacks/handles do not corrupt state; no application restart or manual action is required. Explicit disconnect remains disconnected until reconnect is requested.

## Independent criteria source

The requirement is behavioral rather than numeric here; the 10-second system deadline is measured separately in SYS-002/CON-008.

## Test type and automation rationale

Automation controls the fault and asserts state, but actual radio/power behavior makes this HIL.

## Required instrumentation and observability

Add programmable disconnect/power fixture, state revision logging, stale-handle test mode, and recovery event correlation.

## Evidence retained

State timeline, BLE logs/PCAP, target/boot IDs, poll/history resumption evidence.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
