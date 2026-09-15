<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-003: Alert settings CRUD and server-side validation

Primary type: Browser plus API/database integration  
Execution mode: Automated  
Current feasibility: Blocked; settings UI/API/tables are absent  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-603 | [SCRUM-565](https://pkamp.atlassian.net/browse/SCRUM-565) | SWE-WEB-MLR-603 - Settings Page |
| SWE-WEB-LLR-610 | [SCRUM-584](https://pkamp.atlassian.net/browse/SCRUM-584) | SWE-WEB-LLR-610 - Recipient List UI |
| SWE-WEB-LLR-611 | [SCRUM-585](https://pkamp.atlassian.net/browse/SCRUM-585) | SWE-WEB-LLR-611 - Per-Recipient Threshold UI |
| SWE-WEB-LLR-612 | [SCRUM-586](https://pkamp.atlassian.net/browse/SCRUM-586) | SWE-WEB-LLR-612 - Message Configuration UI |
| SWE-SEC-LLR-754 | [SCRUM-629](https://pkamp.atlassian.net/browse/SCRUM-629) | SWE-SEC-LLR-754 - Input Validation |

## Purpose and usefulness

The test follows real settings workflows and negative API paths, proving validation at the trusted server boundary.

## Profiles and qualification credit

- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-003:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use ADMIN and USER accounts, isolated MySQL, settings page/API, and valid/invalid recipient/rule/control payload corpus.

## Detailed repeatable procedure

1) As ADMIN list, add, edit, enable/disable, and remove multiple email/SMS recipients. 2) Create/update independent min/max Celsius-equivalent thresholds and high/low messages. 3) Restart and verify persistence. 4) As USER repeat mutations through UI and direct API. 5) Submit malformed emails/phones, min greater than or equal to max, unsupported source/sensor, and out-of-range control values. 6) Verify rejected inputs do not persist or execute.

## PASS criteria

All valid fields round-trip and persist; ADMIN CRUD works for every recipient/rule; USER and unauthenticated mutations are denied server-side; every invalid payload receives a clear 4xx response and causes zero database/command changes.

## Independent criteria source

Required fields and authorization come from Jira. Threshold ordering is min < max; format validation should use the selected provider's documented address rules.

## Test type and automation rationale

UI/API/DB checks are deterministic and should be automated.

## Required instrumentation and observability

Implement settings UI/API, database model, shared validation schema, role fixtures, change audit, and test selectors.

## Evidence retained

Browser/API transcript, before/after database dump, validation matrix, audit records.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
