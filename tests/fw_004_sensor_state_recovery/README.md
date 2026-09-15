<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-004: Sensor visible-state machine, disconnect, and recovery

Primary type: Firmware unit plus HIL  
Execution mode: Semi-automated  
Current feasibility: Partially runnable with fake sensors  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-303 | [SCRUM-459](https://pkamp.atlassian.net/browse/SCRUM-459) | SWE-EMB-MLR-303 - Sensor State Model |
| SWE-EMB-MLR-304 | [SCRUM-460](https://pkamp.atlassian.net/browse/SCRUM-460) | SWE-EMB-MLR-304 - Disconnect Transition Behavior |
| SWE-EMB-MLR-312 | [SCRUM-468](https://pkamp.atlassian.net/browse/SCRUM-468) | SWE-EMB-MLR-312 - Automatic Sensor Recovery |
| SWE-EMB-LLR-308 | [SCRUM-478](https://pkamp.atlassian.net/browse/SCRUM-478) | SWE-EMB-LLR-308 - Internal State Separation |
| SWE-EMB-LLR-309 | [SCRUM-479](https://pkamp.atlassian.net/browse/SCRUM-479) | SWE-EMB-LLR-309 - Visible State Mapping |
| SWE-EMB-LLR-310 | [SCRUM-480](https://pkamp.atlassian.net/browse/SCRUM-480) | SWE-EMB-LLR-310 - Fault Entry |
| SWE-EMB-LLR-311 | [SCRUM-481](https://pkamp.atlassian.net/browse/SCRUM-481) | SWE-EMB-LLR-311 - Reconnection State |
| SWE-EMB-LLR-326 | [SCRUM-496](https://pkamp.atlassian.net/browse/SCRUM-496) | SWE-EMB-LLR-326 - Recovery Without Restart |

## Purpose and usefulness

A single transition-table test efficiently covers state derivation, failure handling, and recovery invariants.

## Profiles and qualification credit

- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, verification-firmware, implementation:FW-004:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use scripted valid/fail/recover sensor reads, observable runtime/display state, and the configured one-failure/one-success thresholds.

## Detailed repeatable procedure

1) Start valid with display disabled, then enable it. 2) Inject the configured number of failed reads. 3) Verify numeric validity clears and visible state becomes DISCONNECTED. 4) Attempt a local display toggle while disconnected. 5) Restore valid reads without restarting tasks, BLE, or device. 6) Verify state becomes connected and visible OFF. 7) Repeat independently for both sensors while the other continues. 8) Run the same sequence on real hardware.

## PASS criteria

Visible-state truth table is exact: connected+enabled=ON, connected+disabled=OFF, invalid=DISCONNECTED. Failure invalidates the value; disconnected button presses cannot expose a number; valid recovery occurs without restart and resets display_enabled to false/OFF.

## Independent criteria source

The state truth table and recovery-to-OFF behavior are explicit. Fault thresholds use the released configuration so tests track approved implementation.

## Test type and automation rationale

Automated unit transitions provide exhaustive coverage; real disconnect/reconnect needs HIL confirmation.

## Required instrumentation and observability

Add transition-table unit tests, state-change event hooks, injectable faults, and real-sensor HIL relays.

## Evidence retained

Transition trace, state snapshots, unaffected-sensor log, HIL recovery timing.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
