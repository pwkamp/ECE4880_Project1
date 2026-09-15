<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-005: Celsius/Fahrenheit presentation without storage mutation

Primary type: Unit plus browser integration  
Execution mode: Automated  
Current feasibility: Blocked; web UI absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-WEB-MLR-605 | [SCRUM-567](https://pkamp.atlassian.net/browse/SCRUM-567) | SWE-WEB-MLR-605 - Celsius/Fahrenheit Presentation |
| SWE-WEB-LLR-616 | [SCRUM-590](https://pkamp.atlassian.net/browse/SCRUM-590) | SWE-WEB-LLR-616 - Canonical Conversion |
| SWE-WEB-LLR-617 | [SCRUM-591](https://pkamp.atlassian.net/browse/SCRUM-591) | SWE-WEB-LLR-617 - Unit Switch Refresh |

## Purpose and usefulness

Known points expose offset and scale mistakes across every presentation surface while guarding against accidental database conversion.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-005:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use canonical Celsius DB rows at -10, 0, 22, 50, and 63 C, threshold settings, and a browser unit selector.

## Detailed repeatable procedure

1) Capture database rows. 2) Display current cards, graph, axes, and thresholds in Celsius. 3) Switch to Fahrenheit. 4) Verify values against F=C*9/5+32: 14, 32, 71.6, 122, and 145.4 F. 5) Switch repeatedly and verify no compounding/round-trip drift. 6) Re-read the database and submitted threshold payloads. 7) Test negative and decimal values.

## PASS criteria

Every presented value/label/axis/threshold changes consistently; conversions match the formula within display rounding of at most 0.1 F; switching units never changes canonical Celsius rows or causes cumulative error; Celsius is used in persisted comparisons.

## Independent criteria source

The formula is explicit. A 0.1 F display tolerance matches one-decimal presentation and is far below the measurement tolerances.

## Test type and automation rationale

Pure conversion and DOM assertions are deterministic and should be automated.

## Required instrumentation and observability

Centralize unit conversion/formatting, keep API units explicit, add data attributes for canonical values, and unit/browser vectors.

## Evidence retained

Expected/actual conversion table, DOM/axis snapshots, before/after DB and request payloads.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
