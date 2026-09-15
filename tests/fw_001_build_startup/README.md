<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-001: Firmware clean build matrix and startup initialization

Primary type: Firmware build integration  
Execution mode: Automated  
Current feasibility: Partially runnable; real backends are stubs  
Scaffold status: implemented

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-300 | [SCRUM-456](https://pkamp.atlassian.net/browse/SCRUM-456) | SWE-EMB-MLR-300 - ESP-IDF C Firmware |
| SWE-EMB-LLR-300 | [SCRUM-470](https://pkamp.atlassian.net/browse/SCRUM-470) | SWE-EMB-LLR-300 - Firmware Entry Point |

## Purpose and usefulness

One build matrix catches conditional-compilation and integration omissions more efficiently than separate nearly identical builds.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, esp-idf, device-config.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use pinned ESP-IDF 6.x and configurations for fake/real sensor backend crossed with LED/real display backend.

## Detailed repeatable procedure

1) Generate the firmware header from protocol JSON. 2) Build the four backend combinations from a clean state. 3) Run a static call-path check or instrumented startup test that invokes sensor, display/backlight, input, shared state, history, and BLE initialization from app_main. 4) Fail on unsupported-stub execution in the production configuration. 5) Run size and generated-config drift checks.

## PASS criteria

All four compile-check builds succeed; the production configuration links real implementations rather than stubs; app_main initializes every required subsystem in defined order and propagates failures; generated protocol constants match Python.

## Independent criteria source

The requirements specify toolchain/language/components but no runtime threshold; compile/link success and verified initialization are direct criteria.

## Test type and automation rationale

Build and startup-order assertions are deterministic and should be automated in CI.

## Required instrumentation and observability

Add CI build matrix, production-config stub guard, startup event trace, and firmware Unity test application.

## Evidence retained

Four build logs, size reports, startup trace, generated-file comparison.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
