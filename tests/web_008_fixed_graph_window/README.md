<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-008: Fixed compliance graph axes, 300-second window, and leftward scroll

Primary type: Browser graph test with fake clock  
Execution mode: Automated  
Current feasibility: Blocked; graph UI absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-608 | [SCRUM-570](https://pkamp.atlassian.net/browse/SCRUM-570) | SWE-WEB-MLR-608 - Compliance Graph Y-Axis |
| SWE-WEB-MLR-610 | [SCRUM-572](https://pkamp.atlassian.net/browse/SCRUM-572) | SWE-WEB-MLR-610 - Compliance Graph Time Window |
| SWE-WEB-MLR-614 | [SCRUM-648](https://pkamp.atlassian.net/browse/SCRUM-648) | SWE-WEB-MLR-614 - Chart-Recorder Scrolling Behavior |
| SWE-WEB-LLR-624 | [SCRUM-598](https://pkamp.atlassian.net/browse/SCRUM-598) | SWE-WEB-LLR-624 - Fixed Celsius Axis |
| SWE-WEB-LLR-625 | [SCRUM-599](https://pkamp.atlassian.net/browse/SCRUM-599) | SWE-WEB-LLR-625 - Fixed Fahrenheit Axis |
| SWE-WEB-LLR-626 | [SCRUM-600](https://pkamp.atlassian.net/browse/SCRUM-600) | SWE-WEB-LLR-626 - 300-Second X Axis |
| SWE-WEB-LLR-631 | [SCRUM-650](https://pkamp.atlassian.net/browse/SCRUM-650) | SWE-WEB-LLR-631 - Newest Sample Placement |
| SWE-WEB-LLR-632 | [SCRUM-651](https://pkamp.atlassian.net/browse/SCRUM-651) | SWE-WEB-LLR-632 - Leftward Aging |
| SWE-WEB-LLR-633 | [SCRUM-652](https://pkamp.atlassian.net/browse/SCRUM-652) | SWE-WEB-LLR-633 - Expired Sample Removal |

## Purpose and usefulness

A fake-clock 301-tick test directly proves ordering, eviction, axis limits, and ongoing scrolling in one coherent graph behavior.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-008:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Seed more than 300 timestamped seconds including boundary and missing samples; use browser fake clock and inspectable chart model.

## Detailed repeatable procedure

1) Render Celsius compliance view and inspect Y-axis. 2) switch to Fahrenheit. 3) Inspect X-axis labels and data order. 4) Advance one-second ticks from a known 300-point window. 5) At each tick verify the new sample occupies the rightmost position, existing positions age left, and samples older than 300 seconds are excluded. 6) Continue through 301 updates. 7) Verify missing markers do not alter scrolling.

## PASS criteria

Celsius axis is exactly 10 to 50 C; Fahrenheit axis is exactly 50 to 122 F; X-axis represents 300 seconds ago on the left to 0 on the right; newest is rightmost; one new position appears each second; and no sample older than 300 seconds remains after update.

## Independent criteria source

All numeric limits and time direction/window are explicit Jira values.

## Test type and automation rationale

The chart model and timers are deterministic and should run automatically.

## Required instrumentation and observability

Implement compliance graph, injectable clock, inspectable chart dataset/axes, stable time-series ordering, and 301-tick browser test.

## Evidence retained

Axis/data snapshots at ticks 0/1/300/301, request log, screenshots.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
