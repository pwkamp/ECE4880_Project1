<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-003: Enclosure, orientation, and connected-cable drop survival

Primary type: Full-hardware mechanical acceptance  
Execution mode: Manual  
Current feasibility: Blocked; final enclosure is absent  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-200 | [SCRUM-405](https://pkamp.atlassian.net/browse/SCRUM-405) | SYS-HLR-200 - Physical and Mechanical Robustness |
| HWE-MLR-202 | [SCRUM-423](https://pkamp.atlassian.net/browse/SCRUM-423) | HWE-MLR-202 - Third-Box Enclosure and Drop Survival |
| HWE-MLR-203 | [SCRUM-424](https://pkamp.atlassian.net/browse/SCRUM-424) | HWE-MLR-203 - External Connector Robustness |
| HWE-MLR-215 | [SCRUM-636](https://pkamp.atlassian.net/browse/SCRUM-636) | HWE-MLR-215 - Drop Disconnect Allowance |
| HWE-LLR-202 | [SCRUM-436](https://pkamp.atlassian.net/browse/SCRUM-436) | HWE-LLR-202 - Internal Retention |
| HWE-LLR-203 | [SCRUM-437](https://pkamp.atlassian.net/browse/SCRUM-437) | HWE-LLR-203 - Orientation-Independent Mounting |
| HWE-LLR-223 | [SCRUM-639](https://pkamp.atlassian.net/browse/SCRUM-639) | HWE-LLR-223 - Connected-Cable Drop Acceptance |

## Purpose and usefulness

The orientation and drop requirements stress the same mechanical retention and continuity mechanisms, so a single documented sequence is coherent.

## Profiles and qualification credit

- full-hardware: manual; PARTIAL evidence; capabilities: python, pytest, jsonschema, final-hardware, drop-fixture, human-review, implementation:HW-003:full-hardware.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use a production-equivalent third box with battery, LCD, connectors, and cables; define the stakeholder-specified workbench height and floor surface in the approved procedure before execution.

## Detailed repeatable procedure

1) Photograph and functionally check the unit. 2) Operate it upright, inverted, and on each relevant face for two minutes. 3) Inspect internal retention and wiring. 4) With cables attached, drop the unit once using the approved height/orientation/surface. 5) Record whether cables detach. 6) Reconnect detached cables. 7) Repeat the full functional check, inspect the enclosure/connectors/cables, and open the unit for internal inspection.

## PASS criteria

The powered thermometer works in every orientation; no internal assembly becomes loose; enclosure, connectors, and cables do not break; detached cables are allowed only if they reconnect and function; and all sensor, display, BLE, and power functions pass after the drop.

## Independent criteria source

Pass conditions are taken directly from Jira. Drop height, orientation, and surface must be the approved stakeholder values; they are not safely inventable.

## Test type and automation rationale

Impact geometry and damage inspection require manual full-hardware testing; video and pre/post automated functional checks improve objectivity.

## Required instrumentation and observability

Baseline the missing drop parameters; add production-equivalent enclosure/CAD, internal retention drawing, serialized checklist, and video setup.

## Evidence retained

Approved drop parameters, pre/post logs, photos/video, inspection checklist, unit serial and build revision.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
