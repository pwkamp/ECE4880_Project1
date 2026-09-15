<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-004: Graph series selection, same-sample average, and prominent current values

Primary type: Browser data-visualization integration  
Execution mode: Automated  
Current feasibility: Blocked; graph UI is absent  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-604 | [SCRUM-566](https://pkamp.atlassian.net/browse/SCRUM-566) | SWE-WEB-MLR-604 - Main Graph Page and Series Selection |
| SWE-WEB-MLR-613 | [SCRUM-647](https://pkamp.atlassian.net/browse/SCRUM-647) | SWE-WEB-MLR-613 - Prominent Current Temperature Display |
| SWE-WEB-LLR-613 | [SCRUM-587](https://pkamp.atlassian.net/browse/SCRUM-587) | SWE-WEB-LLR-613 - Series Toggle Controls |
| SWE-WEB-LLR-614 | [SCRUM-588](https://pkamp.atlassian.net/browse/SCRUM-588) | SWE-WEB-LLR-614 - Selected Current Values |
| SWE-WEB-LLR-615 | [SCRUM-589](https://pkamp.atlassian.net/browse/SCRUM-589) | SWE-WEB-LLR-615 - Average Calculation Source |
| SWE-WEB-LLR-630 | [SCRUM-649](https://pkamp.atlassian.net/browse/SCRUM-649) | SWE-WEB-LLR-630 - Large Current-Value Styling |

## Purpose and usefulness

A complete eight-state selection matrix is small and catches coupling bugs; seeded record identities prove average correctness.

## Profiles and qualification credit

- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-004:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Seed timestamped Sensor 1, Sensor 2, and Average records including one invalid sensor; open the graph at phone and desktop widths.

## Detailed repeatable procedure

1) Exercise all eight combinations of three independent series toggles. 2) Verify selected lines and current indicators match the latest same-sample database record. 3) With both valid, verify Average=(S1+S2)/2; invalidate either sensor and verify Average is suppressed/marked unavailable. 4) Confirm Sensor 1 and Sensor 2 valid current values appear in dedicated elements without opening settings/control. 5) Compare computed current-value font size with body text and capture screenshots.

## PASS criteria

Every selection combination renders exactly the chosen series; current indicators use the matching latest record; Average never combines different timestamps and is unavailable unless both are valid; valid Sensor 1/2 values are immediately visible and their computed font size is at least 1.5 times normal body text.

## Independent criteria source

Selection and average rules are explicit. The 1.5x font ratio operationalizes 'visually larger' and should be approved as the UI acceptance baseline.

## Test type and automation rationale

DOM/chart data and styles are machine-verifiable, so this should be automated with screenshot evidence.

## Required instrumentation and observability

Implement graph/current components, stable selectors, exposed chart data adapter, seeded record IDs, visual baseline, and approved typography ratio.

## Evidence retained

Selection matrix, chart-series dump, DOM values/styles, seed rows, screenshots.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
