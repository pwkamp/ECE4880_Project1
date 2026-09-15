<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-008: Accidental standard USB-C connection safety

Primary type: Hardware safety analysis and fault injection  
Execution mode: Semi-automated  
Current feasibility: Blocked by schematics and hardware  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| HWE-MLR-210 | [SCRUM-431](https://pkamp.atlassian.net/browse/SCRUM-431) | HWE-MLR-210 - USB-C Misconnection Protection |
| HWE-LLR-217 | [SCRUM-451](https://pkamp.atlassian.net/browse/SCRUM-451) | HWE-LLR-217 - USB-C VBUS Protection |
| HWE-LLR-218 | [SCRUM-452](https://pkamp.atlassian.net/browse/SCRUM-452) | HWE-LLR-218 - USB-C Signal Isolation |

## Purpose and usefulness

A schematic review catches topology errors while controlled fault injection validates real protection and connector behavior.

## Profiles and qualification credit

- hil-physical: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, hardware-schematics, usb-c-safety-fixture, power-analyzer, implementation:HW-008:hil-physical.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Provide the USB-C schematic/layout, component ratings, third-box and sensor assemblies, USB-C source/host test fixtures, current limiting, oscilloscope, and safe operating limits.

## Detailed repeatable procedure

1) Review pin mapping and protection against standard VBUS and host/device connections. 2) Perform continuity/impedance checks unpowered. 3) Apply foreseeable standard USB-C host/device and powered-cable cases through current-limited fixtures. 4) Capture voltage/current on sensor-signal and ESP32 pins. 5) Repeat with each custom sensor port and cable orientation. 6) Remove the accidental connection and run the full sensor/USB host functional checks.

## PASS criteria

No tested standard USB-C connection drives any signal or ESP32 pin beyond approved absolute maximum/continuous limits; no component exceeds thermal/current ratings; the standard host/device and custom sensor remain undamaged and fully functional afterward.

## Independent criteria source

Jira defines no universal numeric voltage/current limit; PASS must use the selected components' datasheet absolute maxima with an engineering safety margin documented before test.

## Test type and automation rationale

This is safety-relevant hardware work, so a supervised semi-automated bench test with current limiting is more appropriate than an unsupervised automatic test.

## Required instrumentation and observability

Complete schematic/layout, approved fault matrix and limits, current-limited USB-C fixtures, rail probes, and post-test diagnostics.

## Evidence retained

Reviewed schematic, fault matrix, instrument traces, thermal/current observations, pre/post functional logs.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
