<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# CON-007: Startup retrieval of 300 seconds within 10 seconds

Primary type: Full-path performance integration  
Execution mode: Semi-automated  
Current feasibility: Blocked by production MySQL adapter and web history API  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-CONN-MLR-507 | [SCRUM-642](https://pkamp.atlassian.net/browse/SCRUM-642) | SWE-CONN-MLR-507 - Startup History Availability Timing |
| SWE-CONN-LLR-515 | [SCRUM-644](https://pkamp.atlassian.net/browse/SCRUM-644) | SWE-CONN-LLR-515 - Ten-Second Startup Sync Budget |

## Purpose and usefulness

This measures the stakeholder-visible startup outcome across every stage rather than summing optimistic component benchmarks.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, scripted-ble, implementation:CON-007:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Keep a third box available with full buffers before software startup; use production BLE, adapter, MySQL, and web history API with synchronized timing.

## Detailed repeatable procedure

1) Verify 300 records per sensor are present. 2) Start timing at connector process launch. 3) Allow autonomous discovery/authentication. 4) Capture metadata/chunks, persistence completion, first current publication, and web history response. 5) Validate the returned window. 6) Repeat ten cold-start trials and one trial with smaller MTU.

## PASS criteria

In every trial, the web history API can serve the previous 300 seconds and current data within 10.000 seconds of software startup; returned records are ordered, duplicate-free, and status-complete. Smaller MTU still meets the limit or yields an explicitly approved performance exception.

## Independent criteria source

The 300-second content and 10-second deadline are explicit; ten trials are a release confidence screen.

## Test type and automation rationale

Automation controls startup and computes timing, but real BLE and database make the test semi-automated integration/HIL.

## Required instrumentation and observability

Implement production adapter/web API; add process-start marker, stage spans, deterministic preloaded firmware history, and performance report.

## Evidence retained

Ten-trial timing CSV, stage spans, BLE packets, MySQL rows, history API payloads.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
