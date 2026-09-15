<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-001: Current/history APIs and one-hertz browser refresh

Primary type: API and browser integration  
Execution mode: Automated  
Current feasibility: Blocked; frontend is a placeholder  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-600 | [SCRUM-562](https://pkamp.atlassian.net/browse/SCRUM-562) | SWE-WEB-MLR-600 - Computer-Hosted Web Application |
| SWE-WEB-MLR-601 | [SCRUM-563](https://pkamp.atlassian.net/browse/SCRUM-563) | SWE-WEB-MLR-601 - One-Hertz UI Data Refresh |
| SWE-WEB-LLR-600 | [SCRUM-574](https://pkamp.atlassian.net/browse/SCRUM-574) | SWE-WEB-LLR-600 - Current Data API |
| SWE-WEB-LLR-601 | [SCRUM-575](https://pkamp.atlassian.net/browse/SCRUM-575) | SWE-WEB-LLR-601 - History API |
| SWE-WEB-LLR-604 | [SCRUM-578](https://pkamp.atlassian.net/browse/SCRUM-578) | SWE-WEB-LLR-604 - Browser Poll Timer |
| SWE-WEB-LLR-605 | [SCRUM-579](https://pkamp.atlassian.net/browse/SCRUM-579) | SWE-WEB-LLR-605 - No Stale Current Value |

## Purpose and usefulness

API contract and browser polling are tested together so mismatched fields or stale-client behavior cannot pass separately.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-001:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Seed MySQL with current and 300-second history/status rows; start the production web server; use a browser with fake timers and network capture.

## Detailed repeatable procedure

1) Call latest and history endpoints and validate schemas/read-only behavior. 2) Verify latest includes Sensor 1, Sensor 2, average, sensor status, box availability, and display state. 3) Verify history accepts only permitted durations and returns timestamps/status/missing markers. 4) Open the active page and advance five one-second ticks. 5) Count requests and update events. 6) Change database state to unavailable/invalid and confirm the prior number is immediately replaced by status text.

## PASS criteria

Endpoints return only database-backed data with all required fields; history is ordered and bounded; the active page performs one request/update per 1000 ms tick within +/-100 ms under real-time confirmation; invalid/unavailable state never leaves a prior numeric value presented as current; write attempts to read-only endpoints fail.

## Independent criteria source

Nominal 1 Hz is explicit. +/-100 ms reuses the connector timing tolerance as a justified consistency target, not a stakeholder HLR.

## Test type and automation rationale

Fake timers and seeded DB make this automated; a short real-time confirmation guards timer integration.

## Required instrumentation and observability

Implement web server/UI, schemas, test data factory, fake clock, stable selectors, network capture, and stale-value assertion.

## Evidence retained

API payloads, request timing log, DOM snapshots, DB seed, schema-validation result.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
