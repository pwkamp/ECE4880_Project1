<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# ALR-002: NORMAL/HIGH/LOW episode state and duplicate suppression

Primary type: Alert state-machine unit test  
Execution mode: Automated  
Current feasibility: Blocked; evaluator absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-ALR-MLR-705 | [SCRUM-608](https://pkamp.atlassian.net/browse/SCRUM-608) | SWE-ALR-MLR-705 - Alert Repetition Policy |
| SWE-ALR-LLR-711 | [SCRUM-621](https://pkamp.atlassian.net/browse/SCRUM-621) | SWE-ALR-LLR-711 - Alert Episode State |
| SWE-ALR-LLR-712 | [SCRUM-622](https://pkamp.atlassian.net/browse/SCRUM-622) | SWE-ALR-LLR-712 - High Edge Trigger |
| SWE-ALR-LLR-713 | [SCRUM-623](https://pkamp.atlassian.net/browse/SCRUM-623) | SWE-ALR-LLR-713 - Low Edge Trigger |
| SWE-ALR-LLR-714 | [SCRUM-624](https://pkamp.atlassian.net/browse/SCRUM-624) | SWE-ALR-LLR-714 - Rearm In Range |

## Purpose and usefulness

Explicit sequences prove edge behavior and suppression over time rather than a single threshold comparison.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, alert-engine, mysql-test-instance, implementation:ALR-002:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use one rule and provider spy; run the same sequences parameterized over recipients and monitored sources.

## Detailed repeatable procedure

1) Feed NORMAL,NORMAL,HIGH,HIGH,HIGH,NORMAL,HIGH. 2) Verify sends only at the two entries into HIGH. 3) Feed NORMAL,LOW,LOW,NORMAL,LOW and verify two low sends. 4) Feed HIGH directly to LOW and LOW directly to HIGH and verify a send on each new out-of-range state. 5) Insert invalid samples during each state and confirm policy does not create per-second alerts or false normalization. 6) Restart if state persistence is designed and verify approved recovery behavior.

## PASS criteria

State is always one of NORMAL, HIGH, or LOW. A notification occurs only on transition into HIGH or LOW; repeated one-second samples in the same state send none; a valid in-range sample returns state to NORMAL and permits a later new episode.

## Independent criteria source

States and transition policy are verbatim Jira. Invalid-sample treatment across restarts must be documented but must never cause per-second spam.

## Test type and automation rationale

This deterministic finite-state machine belongs in fast automated unit tests.

## Required instrumentation and observability

Implement explicit state machine and storage decision, injectable clock/provider, transition audit, and sequence tests.

## Evidence retained

Transition table, provider-spy calls, state audit, restart behavior record.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
