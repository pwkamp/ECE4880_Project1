<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# CON-006: Reconnect discovery and database availability-state publication

Primary type: Software-in-loop plus HIL  
Execution mode: Semi-automated  
Current feasibility: Partially runnable; concrete state persistence absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-CONN-MLR-506 | [SCRUM-529](https://pkamp.atlassian.net/browse/SCRUM-529) | SWE-CONN-MLR-506 - Automatic BLE Reconnect |
| SWE-CONN-LLR-504 | [SCRUM-539](https://pkamp.atlassian.net/browse/SCRUM-539) | SWE-CONN-LLR-504 - Reconnect Retry Interval |
| SWE-CONN-LLR-513 | [SCRUM-548](https://pkamp.atlassian.net/browse/SCRUM-548) | SWE-CONN-LLR-513 - Connection State Publication |

## Purpose and usefulness

Combining state publication with discovery verifies the shared transition that downstream web software relies on.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, scripted-ble, implementation:CON-006:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use scripted discovery/link events, registered target, database adapter spy/MySQL table, and a real power/RF fault HIL variant.

## Detailed repeatable procedure

1) Start connected and record the published state/revision/last-seen time. 2) Force link loss. 3) Verify unavailable state publishes once per transition and discovery retries every configured two seconds. 4) Make the target visible before the 10-second detection limit. 5) Verify connection/polling resumes and connected state publishes with a higher revision and UTC last-seen time. 6) Repeat a real-device cycle. 7) Ensure stale callbacks do not overwrite newer state.

## PASS criteria

Every availability transition produces an ordered database state record with device, connected/unavailable state, UTC observation/last-seen time, reason, and increasing revision. A newly available compatible box is detected within 10 seconds and polling resumes automatically.

## Independent criteria source

Ten seconds is the requirement ceiling; the two-second retry interval is the released configuration that provides margin.

## Test type and automation rationale

SIL exhausts race cases; a nightly HIL run confirms OS/RF discovery timing.

## Required instrumentation and observability

Define/persist device-state schema, implement adapter method, add transition revision/correlation logs, and power/RF HIL control.

## Evidence retained

State table and adapter trace, revision timeline, discovery attempts, HIL recovery log.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
