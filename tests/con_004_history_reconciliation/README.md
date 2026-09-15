<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# CON-004: History synchronization, reconstructed time, idempotency, and gap reconciliation

Primary type: Software-in-loop plus database integration  
Execution mode: Automated  
Current feasibility: Partially runnable; concrete adapter/reconciliation absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-CONN-MLR-503 | [SCRUM-526](https://pkamp.atlassian.net/browse/SCRUM-526) | SWE-CONN-MLR-503 - Startup History Synchronization |
| SWE-CONN-LLR-505 | [SCRUM-540](https://pkamp.atlassian.net/browse/SCRUM-540) | SWE-CONN-LLR-505 - History Sync Trigger |
| SWE-CONN-LLR-506 | [SCRUM-541](https://pkamp.atlassian.net/browse/SCRUM-541) | SWE-CONN-LLR-506 - History Metadata First |
| SWE-CONN-LLR-507 | [SCRUM-542](https://pkamp.atlassian.net/browse/SCRUM-542) | SWE-CONN-LLR-507 - History Chunk Loop |
| SWE-CONN-LLR-508 | [SCRUM-543](https://pkamp.atlassian.net/browse/SCRUM-543) | SWE-CONN-LLR-508 - History Timestamp Reconstruction |
| SWE-CONN-LLR-509 | [SCRUM-544](https://pkamp.atlassian.net/browse/SCRUM-544) | SWE-CONN-LLR-509 - History De-Duplication |

## Purpose and usefulness

One seeded dataset exercises the connected requirements as a transaction and reveals interactions among ordering, budget, timestamps, and database idempotency.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, scripted-ble, implementation:CON-004:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use known 300-record histories for both sensors, fake monotonic/UTC clocks, failure-injectable BLE client, and isolated MySQL.

## Detailed repeatable procedure

1) Confirm metadata is requested before chunks and ranges stay inside reported oldest/newest sequences. 2) Verify recent-first round-robin retrieval. 3) Fail a chunk twice then allow success; separately fail past retries. 4) Enforce a 10-second total budget and persist partial results when exceeded. 5) Reconstruct timestamps one second apart with newest anchored to receive time; calculate total drift. 6) Sync the same history twice. 7) Create a same-boot gap and verify provisional replacement. 8) Create a new-boot gap and verify preceding provisional rows become no-data.

## PASS criteria

Metadata always precedes chunks; each failed chunk receives no more than two retries; total work stops by 10.000 seconds and retains partial data; 300 reconstructed seconds are monotonic at one-second spacing with no more than two seconds accumulated error; live rows win overlaps; repeated sync adds no duplicates; same-boot and new-boot gaps reconcile exactly as specified.

## Independent criteria source

Two retries, 10 seconds, 300 records, one-second spacing, and two-second total reconstruction error are explicit. The unresolved metadata sub-timeout must be baselined; recommended default is 2.0 seconds within the 10-second budget.

## Test type and automation rationale

Deterministic clocks, failures, and database fixtures make this fully automatable.

## Required instrumentation and observability

Implement adapter upsert/reconciliation; add fake clocks, request trace, controllable delays, test-run isolation, and an approved metadata timeout setting.

## Evidence retained

Request order/retry trace, elapsed timing, reconstructed rows, before/after gap tables, duplicate-count query.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
