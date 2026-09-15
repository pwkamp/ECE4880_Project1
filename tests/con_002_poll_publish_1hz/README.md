<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# CON-002: Monotonic one-hertz polling and complete database publication

Primary type: Software-in-loop plus database integration  
Execution mode: Automated  
Current feasibility: Partially runnable; concrete MySQL adapter absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-CONN-MLR-502 | [SCRUM-525](https://pkamp.atlassian.net/browse/SCRUM-525) | SWE-CONN-MLR-502 - One-Hertz Third-Box Polling |
| SWE-CONN-LLR-501 | [SCRUM-536](https://pkamp.atlassian.net/browse/SCRUM-536) | SWE-CONN-LLR-501 - One-Hertz Poll Scheduler |
| SWE-CONN-LLR-502 | [SCRUM-537](https://pkamp.atlassian.net/browse/SCRUM-537) | SWE-CONN-LLR-502 - Successful Poll Persistence |

## Purpose and usefulness

The test joins timing with persistence so a punctual poll that drops fields or a correct row produced late cannot pass.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, scripted-ble, implementation:CON-002:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use a fake monotonic clock for fast tests, a 300-second real-time run, scripted GET_CURRENT responses, and ephemeral MySQL with the production adapter.

## Detailed repeatable procedure

1) Schedule 300 one-second boundaries. 2) Record scheduled and actual poll times. 3) Return known snapshots containing values, statuses, display flags, boot ID, and sequence. 4) Persist every valid result with UTC receive time and average from the same sample. 5) Inspect all rows and adapter calls. 6) Repeat a short run while shifting wall clock to prove monotonic scheduling. 7) Run one real-time 300-second soak.

## PASS criteria

The 300-second run issues 300 +/-1 polls; every scheduled deviation is within +/-100 ms; wall-clock changes do not shift boundaries; each valid poll creates exactly one database record containing all specified fields; and average uses the same valid pair.

## Independent criteria source

The count and +/-100 ms tolerance are explicit in SWE-CONN-LLR-501. Field/UTC/average rules come from LLR-502.

## Test type and automation rationale

Fake-clock and ephemeral-DB orchestration are deterministic and should be automated, with a nightly real-time confirmation.

## Required instrumentation and observability

Implement production MySQL adapter; add injectable monotonic/wall clocks, poll correlation IDs, row-level test query helpers, and real-time timing report.

## Evidence retained

Scheduled/actual timestamp CSV, adapter trace, MySQL rows, wall-clock-shift log.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
