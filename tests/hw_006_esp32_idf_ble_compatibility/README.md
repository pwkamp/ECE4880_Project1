<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-006: ESP32, ESP-IDF, and BLE platform compatibility

Primary type: Build and static compatibility  
Execution mode: Automated  
Current feasibility: Runnable with ESP-IDF 6.x  
Scaffold status: implemented

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| HWE-MLR-206 | [SCRUM-427](https://pkamp.atlassian.net/browse/SCRUM-427) | HWE-MLR-206 - ESP32 Processing Platform |
| HWE-LLR-209 | [SCRUM-443](https://pkamp.atlassian.net/browse/SCRUM-443) | HWE-LLR-209 - ESP32 BLE Capability |

## Purpose and usefulness

A reproducible clean build plus BOM/datasheet assertion directly proves the selected platform can compile and host the required BLE firmware.

## Profiles and qualification credit

- unit: automated; FULL evidence; capabilities: python, pytest, jsonschema, esp-idf, device-config.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use a clean checkout, pinned ESP-IDF/toolchain, selected ESP32 target/module part number, and generated device configuration.

## Detailed repeatable procedure

1) Verify the BOM selects an ESP32 device with BLE supported by the pinned ESP-IDF version. 2) Generate firmware configuration from the shared JSON. 3) Run fullclean, set-target esp32, build, and size. 4) Fail on warnings promoted by project policy, link errors, partition overflow, missing NimBLE/BLE symbols, or generated-file drift. 5) Archive the toolchain/version and binary manifest.

## PASS criteria

The clean C build succeeds for the selected ESP32 target under the pinned ESP-IDF version, BLE/NimBLE is linked, the application fits the partition, and the module datasheet identifies BLE capability.

## Independent criteria source

The project specifies ESP32, ESP-IDF, and C but no performance threshold. Build success, BLE capability, and partition fit are the appropriate measurable criteria.

## Test type and automation rationale

The behavioral result is deterministic and belongs in CI; only the BOM selection assertion needs initial human approval.

## Required instrumentation and observability

Pin ESP-IDF/toolchain in CI, publish size limits, add warnings-as-errors policy, and commit machine-readable BOM/module metadata.

## Evidence retained

Build log, size report, generated-header diff, toolchain manifest, module datasheet link.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
