<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# DOC-001: Design dossier and full-range capability evidence

Primary type: HITL design review  
Execution mode: Manual  
Current feasibility: Partially runnable  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| PRJ-REQ-001 | [SCRUM-399](https://pkamp.atlassian.net/browse/SCRUM-399) | PRJ-REQ-001 - Design Documentation |
| PRJ-REQ-005 | [SCRUM-653](https://pkamp.atlassian.net/browse/SCRUM-653) | PRJ-REQ-005 - Full-Range Design Verification |
| SYS-HLR-300 | [SCRUM-408](https://pkamp.atlassian.net/browse/SCRUM-408) | SYS-HLR-300 - Temperature Design Range |

## Purpose and usefulness

The project requirement explicitly permits design evidence instead of physically testing the entire range; the review also catches range failures in storage or presentation layers.

## Profiles and qualification credit

- manual: manual; PARTIAL evidence; capabilities: python, pytest, jsonschema, human-review, implementation:DOC-001:manual.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Provide the current architecture, schematics, BOM, component datasheets, interface definitions, database types, display layout, and software numeric representations.

## Detailed repeatable procedure

1) Trace every physical and software component from the architecture and BOM to a drawing or source file. 2) Explain construction, startup, sampling, BLE, persistence, web, control, and alert operation. 3) Build a range table showing sensor rating, analog/digital interface limits, int16 centi-Celsius encoding, calculations, MySQL DECIMAL fields, API serialization, graph bounds, and LCD characters at -10.00 C and +63.00 C. 4) Compute the accuracy/rounding error budget at 0 C and about 22 C. 5) Review assumptions and deviations. 6) Obtain reviewer approval.

## PASS criteria

The dossier is reproducible from released artifacts, describes construction and operation end to end, and shows every selected component and representation supports at least -10 C through +63 C. The combined error budget remains within +/-2 C at 0 C and +/-4 C near 22 C. No full-range environmental test is required.

## Independent criteria source

The range and accuracy limits are verbatim Jira values. The decision not to chamber-test the whole range is PRJ-REQ-005.

## Test type and automation rationale

This is a document/design verification task with engineering judgment, so HITL review is appropriate; arithmetic and schema checks can be automated.

## Required instrumentation and observability

Complete hardware schematics/BOM; add generated protocol/schema range checks and a signed design-review checklist.

## Evidence retained

Approved design dossier, datasheets, calculation sheet, schema/protocol check output, signatures.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
