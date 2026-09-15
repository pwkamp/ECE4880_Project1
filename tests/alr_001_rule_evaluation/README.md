<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# ALR-001: Per-recipient, per-source alert rule evaluation

Primary type: Table-driven unit plus database integration  
Execution mode: Automated  
Current feasibility: Blocked; alert subsystem/tables absent  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-ALR-MLR-700 | [SCRUM-603](https://pkamp.atlassian.net/browse/SCRUM-603) | SWE-ALR-MLR-700 - Email and SMS Delivery |
| SWE-ALR-MLR-701 | [SCRUM-604](https://pkamp.atlassian.net/browse/SCRUM-604) | SWE-ALR-MLR-701 - Per-Recipient Alert Rules |
| SWE-ALR-MLR-702 | [SCRUM-605](https://pkamp.atlassian.net/browse/SCRUM-605) | SWE-ALR-MLR-702 - Configurable Alert Messages |
| SWE-ALR-MLR-704 | [SCRUM-607](https://pkamp.atlassian.net/browse/SCRUM-607) | SWE-ALR-MLR-704 - Valid-Data Alert Evaluation |
| SWE-ALR-MLR-706 | [SCRUM-632](https://pkamp.atlassian.net/browse/SCRUM-632) | SWE-ALR-MLR-706 - Alert Source Scope |
| SWE-ALR-LLR-700 | [SCRUM-610](https://pkamp.atlassian.net/browse/SCRUM-610) | SWE-ALR-LLR-700 - Recipient Types |
| SWE-ALR-LLR-701 | [SCRUM-611](https://pkamp.atlassian.net/browse/SCRUM-611) | SWE-ALR-LLR-701 - Multiple Recipients |
| SWE-ALR-LLR-702 | [SCRUM-612](https://pkamp.atlassian.net/browse/SCRUM-612) | SWE-ALR-LLR-702 - Threshold Rule Fields |
| SWE-ALR-LLR-703 | [SCRUM-613](https://pkamp.atlassian.net/browse/SCRUM-613) | SWE-ALR-LLR-703 - Per-Recipient Evaluation |
| SWE-ALR-LLR-704 | [SCRUM-614](https://pkamp.atlassian.net/browse/SCRUM-614) | SWE-ALR-LLR-704 - High Message Selection |
| SWE-ALR-LLR-705 | [SCRUM-615](https://pkamp.atlassian.net/browse/SCRUM-615) | SWE-ALR-LLR-705 - Low Message Selection |
| SWE-ALR-LLR-709 | [SCRUM-619](https://pkamp.atlassian.net/browse/SCRUM-619) | SWE-ALR-LLR-709 - Invalid Sample Skip |
| SWE-ALR-LLR-710 | [SCRUM-620](https://pkamp.atlassian.net/browse/SCRUM-620) | SWE-ALR-LLR-710 - Average Alert Validity |
| SWE-ALR-LLR-715 | [SCRUM-633](https://pkamp.atlassian.net/browse/SCRUM-633) | SWE-ALR-LLR-715 - Alert Source Enum |

## Purpose and usefulness

A compact table-driven matrix covers combinations and prevents cross-recipient threshold/message leakage.

## Profiles and qualification credit

- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, alert-engine, mysql-test-instance, implementation:ALR-001:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Create enabled EMAIL/SMS recipients and rules with distinct Sensor 1, Sensor 2, and optional Average sources, thresholds, and messages; use captured provider spies.

## Detailed repeatable procedure

1) Load all rules from MySQL. 2) Feed valid samples below, within, and above each rule's own thresholds. 3) Verify all enabled recipients are evaluated, not only the first. 4) Verify high/low configured message selection. 5) Feed disconnected, missing, and invalid samples. 6) For Average, make only one sensor valid, then both valid in the same record. 7) Test each monitored-source enum and invalid source.

## PASS criteria

Every enabled rule/recipient/source is evaluated independently using its own Celsius min/max; matching high/low uses the correct configured text; invalid/unavailable sources cause no provider call; Average is evaluated only from two valid same-record sensors; each rule stores exactly one approved source.

## Independent criteria source

Validity, per-recipient independence, and source/message fields are explicit. Boundary inclusivity must be baselined; recommended policy is alerts for value>max and value<min, matching 'exceeds'/'falls below'.

## Test type and automation rationale

Pure evaluation with provider spies and seeded DB is deterministic and should be automated.

## Required instrumentation and observability

Implement tables/repositories/evaluator, explicit source enum, boundary policy, provider spy, and generated combination tests.

## Evidence retained

Input/output matrix, loaded rule rows, provider-spy calls, invalid-source results.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
