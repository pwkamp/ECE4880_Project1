<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-009: Optional graph-extension approval gate

Primary type: Requirements/configuration gate  
Execution mode: Automated plus HITL approval  
Current feasibility: Runnable as absence check; features not implemented  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-609 | [SCRUM-571](https://pkamp.atlassian.net/browse/SCRUM-571) | SWE-WEB-MLR-609 - Configurable Graph Y-Axis |
| SWE-WEB-MLR-611 | [SCRUM-573](https://pkamp.atlassian.net/browse/SCRUM-573) | SWE-WEB-MLR-611 - Configurable Graph Time Window |
| SWE-WEB-LLR-627 | [SCRUM-601](https://pkamp.atlassian.net/browse/SCRUM-601) | SWE-WEB-LLR-627 - Custom Y-Axis Control |
| SWE-WEB-LLR-628 | [SCRUM-602](https://pkamp.atlassian.net/browse/SCRUM-602) | SWE-WEB-LLR-628 - Custom Time-Window Control |

## Purpose and usefulness

This gate prevents optional implementation ideas from silently violating explicit stakeholder graph requirements.

## Profiles and qualification credit

- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-009:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Provide the approved stakeholder decision for configurable Y/time ranges and the production feature flags/routes.

## Detailed repeatable procedure

1) If no approval exists, inspect UI/routes/config and verify no required compliance view exposes custom Y limits or a window other than 300 seconds. 2) If approval exists, link it and enable only the separate advanced view. 3) Test Celsius-equivalent Y values at -10, +63, min=max, min>max, and out of range. 4) Test time windows at 0, 1, 300, and 301 seconds. 5) Confirm compliance view remains fixed.

## PASS criteria

Without approval, the extension is inaccessible and clearly blocked. With approval, only the separate advanced view accepts -10 through +63 C-equivalent limits with min<max and time 0<window<=300 seconds; invalid values are rejected; the stakeholder compliance view remains fixed.

## Independent criteria source

Bounds and conflicts are explicit Jira text. No extension may pass solely because code exists.

## Test type and automation rationale

Feature/config bounds are automated, while the approval link requires HITL governance.

## Required instrumentation and observability

Add stakeholder-decision field/link, feature flags, separate route, server validation, and CI gate.

## Evidence retained

Approval/deviation link, configuration dump, route/UI evidence, boundary-test results.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
