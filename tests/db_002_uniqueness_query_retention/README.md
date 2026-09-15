<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# DB-002: Sample uniqueness, required query plans, and retention

Primary type: MySQL integrity and performance integration  
Execution mode: Automated  
Current feasibility: Partially runnable; current index omits device_id and retention is absent  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-DB-LLR-551 | [SCRUM-551](https://pkamp.atlassian.net/browse/SCRUM-551) | SWE-DB-LLR-551 - Sample Uniqueness |
| SWE-DB-LLR-552 | [SCRUM-552](https://pkamp.atlassian.net/browse/SCRUM-552) | SWE-DB-LLR-552 - History Index |
| SWE-DB-LLR-553 | [SCRUM-553](https://pkamp.atlassian.net/browse/SCRUM-553) | SWE-DB-LLR-553 - Persistent Retention |

## Purpose and usefulness

This one database fixture exercises the three related guarantees that make history safe, queryable, and bounded.

## Profiles and qualification credit

- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, mysql-test-instance, production-mysql-adapter, implementation:DB-002:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use ephemeral MySQL with production schema, adapter, representative multi-device data, at least several thousand rows, and controlled timestamps.

## Detailed repeatable procedure

1) Insert a real sample, then reinsert the same approved natural key. 2) Verify no second row appears. 3) Insert multiple provisional NULL-identity rows and verify permitted behavior. 4) Run EXPLAIN FORMAT=JSON for latest-sample-per-series and bounded 300-second queries. 5) Confirm the intended composite index is selected and no full table scan occurs. 6) Run retention at ages 299, 300, 600, and 601 seconds. 7) Verify current-window queries remain correct during purge.

## PASS criteria

Duplicate real sample identity is rejected/upserted without an extra row; valid provisional rows coexist; both required query forms use the approved composite index; records younger than 300 seconds remain; records older than 600 seconds are eligible and removed by policy; retention does not create gaps inside the required window.

## Independent criteria source

Uniqueness, query forms, 300-second floor, and >600-second eligibility are explicit. Index shape must match the approved device/series storage model.

## Test type and automation rationale

Integrity, plans, and clocked retention are fully automatable against isolated MySQL.

## Required instrumentation and observability

Add composite device/time index, production queries, retention job with injected clock/dry-run, adapter upserts, and plan assertions.

## Evidence retained

Before/after row counts, duplicate error/upsert result, EXPLAIN JSON, retention audit.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
