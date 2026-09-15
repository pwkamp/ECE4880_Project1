<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-007: Admin remote-display controls, confirmed result, and display-enable semantics

Primary type: Browser/API integration plus HIL  
Execution mode: Semi-automated  
Current feasibility: Blocked by web UI and real LCD; connector REST path exists  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-607 | [SCRUM-569](https://pkamp.atlassian.net/browse/SCRUM-569) | SWE-WEB-MLR-607 - Control Page |
| SWE-WEB-MLR-612 | [SCRUM-630](https://pkamp.atlassian.net/browse/SCRUM-630) | SWE-WEB-MLR-612 - Sensor ON/OFF Control Semantics |
| SWE-WEB-LLR-602 | [SCRUM-576](https://pkamp.atlassian.net/browse/SCRUM-576) | SWE-WEB-LLR-602 - Display Control API |
| SWE-WEB-LLR-603 | [SCRUM-577](https://pkamp.atlassian.net/browse/SCRUM-577) | SWE-WEB-LLR-603 - Command Status API |
| SWE-WEB-LLR-622 | [SCRUM-596](https://pkamp.atlassian.net/browse/SCRUM-596) | SWE-WEB-LLR-622 - Sensor Display Controls |
| SWE-WEB-LLR-623 | [SCRUM-597](https://pkamp.atlassian.net/browse/SCRUM-597) | SWE-WEB-LLR-623 - Control State Confirmation |
| SWE-WEB-LLR-629 | [SCRUM-631](https://pkamp.atlassian.net/browse/SCRUM-631) | SWE-WEB-LLR-629 - Remote Sensor Toggle Semantics |

## Purpose and usefulness

The sequence verifies the ambiguous 'sensor power' phrase is implemented as display control and protects users from false confirmation.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-007:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use ADMIN/USER sessions, both valid sensors, production control API, connector, firmware, and observable LCD.

## Detailed repeatable procedure

1) As ADMIN toggle Sensor 1 and Sensor 2 independently. 2) Verify submitted command is SET_DISPLAY/display-enable, not sensor power gating. 3) Delay one BLE response and force one failure. 4) Confirm the UI remains pending and then reflects returned command/current state. 5) Verify failed command does not display success. 6) Attempt direct API calls as USER/unauthenticated. 7) Observe that sensor acquisition/history continues while its display is OFF.

## PASS criteria

Each ADMIN control affects only its sensor's LCD display-enabled state; UI state comes from confirmed result/current state, not optimism; failures remain visible and do not change confirmed state; USER/unauthenticated requests are denied; display OFF does not stop acquisition.

## Independent criteria source

SET_DISPLAY semantics are the current approved interpretation in Jira. Timing is measured separately in SYS-003.

## Test type and automation rationale

Browser/API behavior can be automated; physical LCD and continuing acquisition make the release test HIL.

## Required instrumentation and observability

Implement web control UI/API and chosen IPC, add operation correlation/pending UI hooks, auth fixtures, acquisition counters, and LCD observer.

## Evidence retained

Browser video/log, API/operation transcript, BLE packets, acquisition/history counters, LCD capture.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
