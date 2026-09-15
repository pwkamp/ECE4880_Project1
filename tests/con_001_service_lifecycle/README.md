<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# CON-001: Independent connector service and lifecycle API

Primary type: Software integration test  
Execution mode: Automated  
Current feasibility: Runnable with no-op database and mocked BLE  
Scaffold status: implemented

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-CONN-MLR-500 | [SCRUM-523](https://pkamp.atlassian.net/browse/SCRUM-523) | SWE-CONN-MLR-500 - Three-Component Computer Architecture |
| SWE-CONN-MLR-501 | [SCRUM-524](https://pkamp.atlassian.net/browse/SCRUM-524) | SWE-CONN-MLR-501 - Separate BLE Connection Process |
| SWE-CONN-LLR-500 | [SCRUM-535](https://pkamp.atlassian.net/browse/SCRUM-535) | SWE-CONN-LLR-500 - Connection Worker Executable |

## Purpose and usefulness

Process separation and lifecycle ownership are architectural properties best proven by launching real processes rather than only importing classes.

## Profiles and qualification credit

- unit: automated; FULL evidence; capabilities: python, pytest, jsonschema, fastapi.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, scripted-ble, implementation:CON-001:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Launch the connector as its own process with mock BLE and instrumented database adapter; run a separate web-server test process.

## Detailed repeatable procedure

1) Start the connector entry point and wait for health readiness. 2) Verify it owns a main event loop and one adapter lifecycle. 3) Exercise health, status, scan, connect, pair, disconnect, reconnect, current, display, history, and operation endpoints. 4) Stop/restart the web process while connector polling continues. 5) Stop the connector and confirm clean client/adapter shutdown. 6) Verify API binds only to configured loopback by default.

## PASS criteria

Connector runs independently from the web process, initializes/closes its own BLE and database resources exactly once, serves the documented contracts, survives web-process restart, and shuts down without orphan operations.

## Independent criteria source

Separate execution and endpoints are explicit. Loopback binding reflects the released architecture, while internet access belongs to the web server.

## Test type and automation rationale

The environment is entirely controllable, so this integration test should be automated.

## Required instrumentation and observability

Add subprocess test harness, health/readiness contract, adapter/client lifecycle spies, and process-leak checks.

## Evidence retained

Process IDs, endpoint transcript, lifecycle call counts, shutdown logs.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
