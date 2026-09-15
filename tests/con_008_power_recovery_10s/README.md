<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# CON-008: Running-software recovery after third-box power-on within 10 seconds

Primary type: Hardware-in-the-loop performance  
Execution mode: Semi-automated  
Current feasibility: Partially runnable; external persistence missing  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-CONN-MLR-508 | [SCRUM-643](https://pkamp.atlassian.net/browse/SCRUM-643) | SWE-CONN-MLR-508 - Third-Box Power-On Recovery Timing |
| SWE-CONN-LLR-516 | [SCRUM-645](https://pkamp.atlassian.net/browse/SCRUM-645) | SWE-CONN-LLR-516 - Ten-Second Power-On Recovery Budget |

## Purpose and usefulness

This directly tests the powered-off startup case and priority ordering, which differ from ordinary link reconnection.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- hil-physical: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, ble, power-relay, mysql, implementation:CON-008:hil-physical.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Run connector/database/web continuously with the registered third box OFF; use relay power control and synchronized stage/event capture.

## Detailed repeatable procedure

1) Confirm repeated discovery while the box is OFF. 2) Trigger power ON and timestamp the electrical edge. 3) Measure advertisement discovery, connect, bond reuse/auth, first GET_CURRENT, database commit, and web current availability. 4) Verify history starts without delaying current publication. 5) Repeat ten trials including one new boot and one transient failed scan.

## PASS criteria

Every trial publishes valid current and graph-usable data to the web path within 10.000 seconds of the power edge; current publication precedes or is not blocked by bulk history; transient discovery failure recovers without user input.

## Independent criteria source

The 10-second limit is explicit. First-current priority reflects the current architecture and prevents a full history transfer from hiding deadline failure.

## Test type and automation rationale

Relay and timestamps automate measurement, while real boot/advertising make the test HIL.

## Required instrumentation and observability

Add relay, electrical-edge input, stage telemetry, production adapter/web probe, and controllable scan-failure hook.

## Evidence retained

Power/stage timeline, current/history publication order, DB/API evidence, ten-trial summary.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
