<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# BLE-003: History metadata, chronological chunks, and MTU adaptation

Primary type: Software-in-loop plus BLE HIL  
Execution mode: Semi-automated  
Current feasibility: Largely runnable; dedicated firmware tests absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| INT-MLR-404 | [SCRUM-503](https://pkamp.atlassian.net/browse/SCRUM-503) | INT-MLR-404 - Historical Data Transaction |
| INT-LLR-407 | [SCRUM-514](https://pkamp.atlassian.net/browse/SCRUM-514) | INT-LLR-407 - GET_HISTORY_META Opcode |
| INT-LLR-408 | [SCRUM-515](https://pkamp.atlassian.net/browse/SCRUM-515) | INT-LLR-408 - GET_HISTORY_CHUNK Opcode |
| INT-LLR-409 | [SCRUM-516](https://pkamp.atlassian.net/browse/SCRUM-516) | INT-LLR-409 - History Chunk Response |
| INT-LLR-410 | [SCRUM-517](https://pkamp.atlassian.net/browse/SCRUM-517) | INT-LLR-410 - History Chunk Size |
| INT-LLR-411 | [SCRUM-518](https://pkamp.atlassian.net/browse/SCRUM-518) | INT-LLR-411 - MTU Negotiation |

## Purpose and usefulness

Known patterned buffers expose off-by-one, wrap, truncation, and MTU bugs in one coherent transfer test.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, ble, verification-firmware, implementation:BLE-003:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Populate both 300-record firmware buffers with known sequences/statuses; use central configurations for preferred MTU 247 and smaller negotiated MTUs.

## Detailed repeatable procedure

1) Request metadata and verify boot ID, newest/oldest sequences, and per-sensor counts. 2) Ensure metadata precedes chunk requests. 3) Request full histories by sequence. 4) Decode only complete seven-byte records and verify sensor/start/count/record-size fields. 5) Repeat across circular wrap. 6) Negotiate progressively smaller MTUs and verify requested/returned complete-record counts shrink to fit. 7) Confirm no transaction assumes all 300 records fit one ATT payload.

## PASS criteria

Both histories reconstruct exactly in chronological order with no duplicate/missing sequence inside available ranges; metadata matches buffers; every packet fits negotiated MTU and contains only complete records; preferred MTU is requested when supported; up to 32 records per chunk is never exceeded.

## Independent criteria source

Capacity 300, preferred MTU 247, maximum 32 records, and record layouts come from released protocol JSON.

## Test type and automation rationale

Most vectors run in SIL; a smaller real-MTU case is retained as HIL because platform negotiation behavior matters.

## Required instrumentation and observability

Add firmware history seeding hook, MTU-controllable central, PCAP size checker, and generated cross-language vectors.

## Evidence retained

Metadata/chunk packets, reconstructed histories, MTU matrix, expected/actual sequence report.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
