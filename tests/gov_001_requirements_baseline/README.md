<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# GOV-001: Requirements baseline, ambiguity, and deviation gate

Primary type: HITL requirements review  
Execution mode: Manual  
Current feasibility: Runnable now  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| PRJ-REQ-003 | [SCRUM-401](https://pkamp.atlassian.net/browse/SCRUM-401) | PRJ-REQ-003 - Requirements Compliance |
| PRJ-REQ-004 | [SCRUM-402](https://pkamp.atlassian.net/browse/SCRUM-402) | PRJ-REQ-004 - Requirements Clarification |

## Purpose and usefulness

A frozen baseline prevents passing a convenient implementation while silently testing stale or contradictory requirement text.

## Profiles and qualification credit

- manual: manual; PARTIAL evidence; capabilities: python, pytest, jsonschema, human-review, implementation:GOV-001:manual.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Export all approved Jira Requirement issues; record the repository commit; provide the stakeholder decision log and traceability template.

## Detailed repeatable procedure

1) Export the SCRUM Requirement issue type and sort by Jira key. 2) Confirm 255 requirements and capture UID, level, status, text, hierarchy links, and source. 3) Diff the export against the prior baseline. 4) Search for unresolved brackets or conflicts, including all [N] values, fixed-versus-configurable graph ranges, MySQL queue versus localhost REST, device_id omission, and database status vocabulary. 5) Assign an owner and due date to each open decision. 6) Link every approved deviation to the affected requirements and tests. 7) Freeze the export and commit SHA used by the test run.

## PASS criteria

Exactly 255 approved requirements are present: 5 Project, 18 HLR, 76 MLR, and 156 LLR. Every requirement maps to at least one test, every open ambiguity or conflict has a named owner and disposition, and no dependent test is reported PASS while its criterion is unresolved.

## Independent criteria source

Counts come from the direct Jira export on 2026-09-10. The no-unresolved-criterion rule is necessary for an auditable PASS decision.

## Test type and automation rationale

Human review is required because stakeholder intent and deviation approval cannot be inferred by code; the completeness and duplicate checks should still be scripted.

## Required instrumentation and observability

Add a versioned requirements export, a machine-readable traceability file, a decision/deviation register, and a CI check for missing/duplicate UIDs and unresolved [N] tokens.

## Evidence retained

Jira export, export hash, coverage report, decision log, reviewer names/date, repository SHA.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
