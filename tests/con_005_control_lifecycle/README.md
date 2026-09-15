<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# CON-005: Control IPC or queue worker lifecycle and completion

Primary type: Database integration plus HIL  
Execution mode: Semi-automated  
Current feasibility: Blocked by architecture decision; current repo uses REST instead of required MySQL queue  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-CONN-MLR-505 | [SCRUM-528](https://pkamp.atlassian.net/browse/SCRUM-528) | SWE-CONN-MLR-505 - Control Command Relay |
| SWE-CONN-LLR-510 | [SCRUM-545](https://pkamp.atlassian.net/browse/SCRUM-545) | SWE-CONN-LLR-510 - Pending Command Poll |
| SWE-CONN-LLR-511 | [SCRUM-546](https://pkamp.atlassian.net/browse/SCRUM-546) | SWE-CONN-LLR-511 - Command Claiming |
| SWE-CONN-LLR-512 | [SCRUM-547](https://pkamp.atlassian.net/browse/SCRUM-547) | SWE-CONN-LLR-512 - Command Completion |

## Purpose and usefulness

The test protects against duplicate physical actions, permanently stuck commands, and a design/requirement mismatch; merely testing a REST 200 response would be misleading.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, control-path-decision, verification-firmware, ble, implementation:CON-005:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

First approve either the Jira MySQL queue requirements or a linked stakeholder deviation to REST. If queue retained, use isolated MySQL, connector worker, and controllable BLE/display result.

## Detailed repeatable procedure

1) Insert a PENDING command through the web path. 2) Measure polling intervals and atomic PENDING-to-IN_PROGRESS claim. 3) Verify execution occurs only after exactly one affected row. 4) Record SUCCEEDED/FAILED, completion UTC, result, and confirmed device state. 5) Restart after claim and verify abandoned IN_PROGRESS recovery. 6) Keep the device unavailable and verify stale PENDING becomes EXPIRED. 7) Attempt duplicate claim/replay. 8) Run the same observable lifecycle through the approved REST design if that deviation is accepted.

## PASS criteria

The implemented path matches the approved requirement baseline. If queue retained: poll interval is at most 250 ms, exactly one execution follows one atomic claim, every command reaches PENDING/IN_PROGRESS/SUCCEEDED/FAILED/EXPIRED as applicable, completion/result are durable, replay does not re-execute, and stale commands transition by approved N values. Recommended baselines are 2 seconds pending TTL and 5 seconds in-progress abandonment until stakeholders approve.

## Independent criteria source

250 ms and state names are explicit. The two [N] values are unresolved; proposed 2/5 seconds provide margin over the normal sub-one-second action while bounding stale work, but they require approval before formal PASS.

## Test type and automation rationale

Database lifecycle checks can be automated, while confirmed physical display execution requires HIL.

## Required instrumentation and observability

Resolve Jira deviation; implement chosen queue or update requirements; add command IDs/correlation, atomic-claim SQL, TTL worker, recovery hooks, and display observer.

## Evidence retained

Decision link, SQL transition log, affected-row counts, restart/expiry timeline, BLE/display result.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
