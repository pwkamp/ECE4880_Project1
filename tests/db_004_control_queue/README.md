<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# DB-004: Control-command queue schema, lifecycle, and expiry

Primary type: MySQL state-machine integration  
Execution mode: Automated  
Current feasibility: Blocked by REST-versus-queue decision and absent table  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-DB-MLR-553 | [SCRUM-533](https://pkamp.atlassian.net/browse/SCRUM-533) | SWE-DB-MLR-553 - Control Command Queue |
| SWE-DB-LLR-557 | [SCRUM-557](https://pkamp.atlassian.net/browse/SCRUM-557) | SWE-DB-LLR-557 - control_commands Table |
| SWE-DB-LLR-558 | [SCRUM-558](https://pkamp.atlassian.net/browse/SCRUM-558) | SWE-DB-LLR-558 - Command Status Values |

## Purpose and usefulness

A clocked database state-machine test catches illegal or stuck transitions before physical commands are involved.

## Profiles and qualification credit

- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, mysql-test-instance, production-mysql-adapter, implementation:DB-004:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

If the queue requirements remain approved, use ephemeral MySQL, injected UTC clock, web command repository, and worker claim/completion repository.

## Detailed repeatable procedure

1) Insert a Sensor 1 ON command and inspect all fields. 2) Atomically claim it with a conditional update. 3) Complete one SUCCEEDED and one FAILED command with completion/result. 4) Attempt invalid target/state and illegal state transitions. 5) Advance the clock past approved pending N and verify EXPIRED. 6) Advance past approved in-progress N and verify FAILED/abandoned policy. 7) Restart repositories and confirm durability.

## PASS criteria

The table contains target sensor, desired display state, requested UTC, exact execution-state enum, completion UTC, and result. Only PENDING, IN_PROGRESS, SUCCEEDED, FAILED, and EXPIRED are accepted; legal conditional transitions affect one row; stale commands leave PENDING/IN_PROGRESS within approved N; all state is durable.

## Independent criteria source

Fields and exact states are explicit. Pending/in-progress N values require approval; proposed defaults are 2 seconds and 5 seconds, respectively.

## Test type and automation rationale

It is deterministic and should run automatically if the queue remains in scope.

## Required instrumentation and observability

Resolve architecture; add migration/table, repository, conditional transitions, UTC injected clock, TTL/abandonment worker, and transition constraints.

## Evidence retained

Rows at each state, affected-row counts, restart readback, expiry timeline, negative constraint results.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
