<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-009: Unified local/remote display state path and invalid-command protection

Primary type: Firmware unit and software-in-loop  
Execution mode: Automated  
Current feasibility: Mostly runnable in current logic  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-313 | [SCRUM-469](https://pkamp.atlassian.net/browse/SCRUM-469) | SWE-EMB-MLR-313 - Remote Display Command Handling |
| SWE-EMB-LLR-327 | [SCRUM-497](https://pkamp.atlassian.net/browse/SCRUM-497) | SWE-EMB-LLR-327 - Remote/Local Shared State |
| SWE-EMB-LLR-328 | [SCRUM-498](https://pkamp.atlassian.net/browse/SCRUM-498) | SWE-EMB-LLR-328 - Remote Command Validation |

## Purpose and usefulness

Equivalence and negative vectors prove the paths are truly shared and fail closed rather than just reaching similar visible outcomes.

## Profiles and qualification credit

- unit: automated; FULL evidence; capabilities: python, pytest, jsonschema, firmware-unity, implementation:FW-009:unit.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use mock display renderer, direct local-toggle entry point, protocol SET_DISPLAY handler, and complete valid/invalid command vectors.

## Detailed repeatable procedure

1) Set a known sensor state through the local entry point and capture mutated fields/render call. 2) Reach the same target through remote SET_DISPLAY and compare state/render output. 3) Repeat both directions for both sensors. 4) Send sensor IDs 0, 3, and 255 plus non-Boolean state bytes. 5) Send malformed payload lengths. 6) Compare before/after snapshots and response statuses.

## PASS criteria

Local and remote operations update the same display_enabled fields and invoke the same renderer. Every invalid identifier/value/length returns the specified error and changes no runtime, display, history, or boot state.

## Independent criteria source

Valid IDs are 1 and 2; Boolean values are 0 and 1; response statuses come from protocol version 2.

## Test type and automation rationale

These deterministic state mutations belong in fully automated unit/SIL testing.

## Required instrumentation and observability

Add C unit tests around both entry points, renderer spy, before/after state hashing, and malformed-packet corpus.

## Evidence retained

Vector list, statuses, state hashes, render-spy calls.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
