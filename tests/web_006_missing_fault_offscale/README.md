<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-006: Disconnected, no-data, missing, and valid off-scale representation

Primary type: Browser functional plus visual review  
Execution mode: Semi-automated  
Current feasibility: Blocked; UI absent and DB vocabulary unresolved  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-606 | [SCRUM-568](https://pkamp.atlassian.net/browse/SCRUM-568) | SWE-WEB-MLR-606 - Missing/Unavailable Presentation |
| SWE-WEB-LLR-618 | [SCRUM-592](https://pkamp.atlassian.net/browse/SCRUM-592) | SWE-WEB-LLR-618 - Unplugged Sensor Text |
| SWE-WEB-LLR-619 | [SCRUM-593](https://pkamp.atlassian.net/browse/SCRUM-593) | SWE-WEB-LLR-619 - No Data Available Text |
| SWE-WEB-LLR-620 | [SCRUM-594](https://pkamp.atlassian.net/browse/SCRUM-594) | SWE-WEB-LLR-620 - Graph Missing Gap |
| SWE-WEB-LLR-621 | [SCRUM-595](https://pkamp.atlassian.net/browse/SCRUM-595) | SWE-WEB-LLR-621 - Off-Scale Marker |

## Purpose and usefulness

The paired fixtures prove the UI distinguishes semantic absence from valid values outside the viewport, a common charting failure.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-006:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Seed four distinct states: disconnected sensor, box unavailable, missing/provisional graph sample, and valid samples below/above the fixed axis.

## Detailed repeatable procedure

1) Show a valid current number. 2) Switch to disconnected and verify textual sensor-unplugged presentation. 3) Switch box unavailable and verify exact text. 4) Render a history series with an interior missing sample. 5) Render valid 9 C and 51 C samples against the 10-50 C axis. 6) Inspect chart data and pixels/accessible labels. 7) Return to valid and confirm recovery.

## PASS criteria

Disconnected current displays 'Sensor X Unplugged' or the approved exact equivalent; box unavailable displays exactly 'No data available'; missing data is a gap/dedicated missing marker with no connecting line; valid off-scale points retain valid identity and show a boundary/clipped indication distinct from missing; stale numbers disappear immediately.

## Independent criteria source

The box text is exact in Jira. Sensor wording permits the stated example/equivalent. Off-scale values 9/51 are minimal valid excursions that unambiguously cross fixed bounds.

## Test type and automation rationale

Data-state assertions are automated; chart visual semantics receive HITL screenshot review.

## Required instrumentation and observability

Reconcile DB/API status vocabulary; implement semantic chart points, accessible labels, screenshot baselines, and stale-DOM checks.

## Evidence retained

Seed payloads, chart data dump, DOM text, screenshots, reviewer decision.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
