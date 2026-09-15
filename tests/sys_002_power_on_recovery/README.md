<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# SYS-002: Power-on recovery and historical availability within 10 seconds

Primary type: Full-system HIL timing  
Execution mode: Semi-automated  
Current feasibility: Partially runnable; external persistence and web are missing  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-520 | [SCRUM-416](https://pkamp.atlassian.net/browse/SCRUM-416) | SYS-HLR-520 - Startup and Recovery |

## Purpose and usefulness

The scenario measures the actual user-visible deadline and includes the costly discovery, BLE, database, and web stages that unit tests cannot validate together.

## Profiles and qualification credit

- hil-physical: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, power-relay, mysql, web-console, implementation:SYS-002:hil-physical.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Keep the connector/database/web software running. Prepare a third box with a populated 300-record buffer and a remotely controlled power switch. Synchronize the test controller, connector, database, and browser clocks.

## Detailed repeatable procedure

1) With the third box OFF, verify the software remains in unavailable/discovering state. 2) Start high-resolution event capture. 3) Turn the third box ON through the relay and record the electrical power edge. 4) Wait for BLE discovery, connection, authentication, first current publication, history persistence, and web availability. 5) Repeat ten times from a clean connection state. 6) Include one run after a new boot ID and one with a full history buffer.

## PASS criteria

For all ten trials, required current information becomes usable by the web application no later than 10.000 seconds after the measured power-on edge. The run with available history also exposes the recoverable recent 300 seconds within the same 10.000-second budget; failures retain gaps rather than stale values.

## Independent criteria source

The hard 10-second limit is stated in the HLRs and shared protocol configuration; ten trials reduce the chance of accepting a one-off favorable result without inventing a percentile requirement.

## Test type and automation rationale

A relay and event logger make timing repeatable, while physical power cycling keeps this an HIL test.

## Required instrumentation and observability

Add relay control, monotonic stage timestamps with a common correlation ID, MySQL/web readiness probes, and an automated timing report.

## Evidence retained

Power traces, per-stage timestamp CSV, DB rows, API responses, browser capture, ten-trial summary.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
