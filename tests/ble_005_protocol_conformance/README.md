<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# BLE-005: Protocol header, request ID, version, and status conformance

Primary type: Protocol unit and fuzz test  
Execution mode: Automated  
Current feasibility: Runnable; current Python tests cover core cases  
Scaffold status: implemented

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| INT-MLR-407 | [SCRUM-506](https://pkamp.atlassian.net/browse/SCRUM-506) | INT-MLR-407 - Protocol Versioning and Error Reporting |
| INT-LLR-402 | [SCRUM-509](https://pkamp.atlassian.net/browse/SCRUM-509) | INT-LLR-402 - Request Identifier |
| INT-LLR-403 | [SCRUM-510](https://pkamp.atlassian.net/browse/SCRUM-510) | INT-LLR-403 - Protocol Header |
| INT-LLR-412 | [SCRUM-519](https://pkamp.atlassian.net/browse/SCRUM-519) | INT-LLR-412 - Status Codes |
| INT-LLR-413 | [SCRUM-520](https://pkamp.atlassian.net/browse/SCRUM-520) | INT-LLR-413 - Unsupported Version Handling |

## Purpose and usefulness

Cross-language golden vectors and negative fuzzing target interoperability and fail-closed behavior rather than arbitrary code coverage.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- cross-language: automated; FULL evidence; capabilities: python, pytest, jsonschema, c-compiler, node, npm, pr1-console.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Generate Python and C constants from protocol JSON; use golden packets and a bounded malformed-message/fuzz corpus.

## Detailed repeatable procedure

1) Encode/decode every opcode and response status in little endian. 2) Verify the eight-byte header fields and payload lengths. 3) Send concurrent request IDs and confirm exact echo/matching. 4) Exercise SUCCESS, INVALID_COMMAND, INVALID_SENSOR, INVALID_VALUE, NOT_AVAILABLE, INTERNAL_ERROR, and auth statuses. 5) Send unsupported protocol versions for read and state-changing commands. 6) Send truncated, overlong, and inconsistent-length packets. 7) Compare Python and C golden vectors.

## PASS criteria

Both implementations agree byte-for-byte; responses echo opcode/request ID; every mandatory status is representable/surfaced; malformed or unsupported-version packets are rejected; and no state-changing command is applied after a version or validation failure.

## Independent criteria source

Header size, little-endian rule, version 2, opcodes, layouts, and status codes come from the shared protocol JSON.

## Test type and automation rationale

Deterministic byte layouts are ideal for fast automated unit/CI tests.

## Required instrumentation and observability

Add generated golden vectors consumed by Python and C, C protocol unit target, mutation corpus, and state-hash oracle.

## Evidence retained

Golden packet files, fuzz seed/version, status matrix, before/after state hashes.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
