<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# SYS-003: Remote per-sensor display control under one second

Primary type: Full-system HIL timing  
Execution mode: Semi-automated  
Current feasibility: Blocked by physical LCD and unresolved queue-versus-REST decision  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-510 | [SCRUM-415](https://pkamp.atlassian.net/browse/SCRUM-415) | SYS-HLR-510 - Remote Third-Box Display Control |
| INT-LLR-416 | [SCRUM-646](https://pkamp.atlassian.net/browse/SCRUM-646) | INT-LLR-416 - Remote Control End-to-End Timing |

## Purpose and usefulness

End-to-end timing is the useful property; testing only the BLE call or button handler would miss queue, scheduling, rendering, and confirmation delays.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- hil-physical: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, ble, lcd, browser, implementation:SYS-003:hil-physical.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use production-path web control, server, selected IPC design, connector, BLE, firmware, and physical LCD. Instrument the UI action and LCD with a synchronized event logger or high-frame-rate camera.

## Detailed repeatable procedure

1) Confirm both sensors are valid and displayed. 2) For Sensor 1, submit OFF then ON; repeat for Sensor 2. 3) Execute ten transitions per sensor/state combination. 4) Measure from accepted computer user action to the first physical LCD frame showing the requested state. 5) Verify the web page waits for command/current confirmation. 6) Repeat once during concurrent history synchronization. 7) Attempt an unauthorized request and an invalid sensor request.

## PASS criteria

Every authorized transition changes only the selected sensor and completes in less than 1.000 second; the returned/current state equals the physical LCD; display work preempts history as designed; unauthorized or invalid requests cause no local state change. No optimistic UI state is treated as completion.

## Independent criteria source

The one-second threshold is explicit in SYS-HLR-510 and INT-LLR-416. The repository's 0.9-second connector timeout is an internal margin, not a replacement acceptance limit.

## Test type and automation rationale

Semi-automated HIL is appropriate because scripts can issue requests and compute latency, but the physical LCD edge must be observed.

## Required instrumentation and observability

Select and implement the approved IPC path; add correlation IDs through UI/server/command/BLE/firmware; expose monotonic timestamps; integrate the real LCD and optical/camera trigger.

## Evidence retained

Per-trial latency log, camera/photodiode trace, command records, BLE trace, UI/API results.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
