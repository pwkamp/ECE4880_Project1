<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-005: Battery peak-current margin and switch-off behavior

Primary type: Hardware-in-the-loop power measurement  
Execution mode: Semi-automated  
Current feasibility: Blocked by final power design  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-220 | [SCRUM-407](https://pkamp.atlassian.net/browse/SCRUM-407) | SYS-HLR-220 - Third-Box Power Control |
| HWE-MLR-205 | [SCRUM-426](https://pkamp.atlassian.net/browse/SCRUM-426) | HWE-MLR-205 - Battery and Power Switch |
| HWE-LLR-207 | [SCRUM-441](https://pkamp.atlassian.net/browse/SCRUM-441) | HWE-LLR-207 - Battery Supply Capacity |
| HWE-LLR-208 | [SCRUM-442](https://pkamp.atlassian.net/browse/SCRUM-442) | HWE-LLR-208 - Physical OFF State |

## Purpose and usefulness

Power integrity and true OFF behavior depend on transient hardware loads and cannot be established from nominal datasheet current alone.

## Profiles and qualification credit

- hil-physical: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, final-power-design, power-analyzer, power-relay, implementation:HW-005:hil-physical.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use production battery/regulator/switch, electronic load or current analyzer, oscilloscope, real sensors/LCD, and worst-case radio/display activity.

## Detailed repeatable procedure

1) Record battery voltage/state and regulator ratings. 2) Measure average and peak current while advertising, connected idle, 1 Hz polling, history sync, and maximum backlight. 3) Exercise simultaneous BLE, both sensors, and display updates. 4) Verify rails remain within component limits and capture brownout/reset counters. 5) Toggle the physical switch OFF while a remote client polls. 6) Observe ESP32/LCD rails and remote data. 7) Restore power and verify normal startup.

## PASS criteria

Measured simultaneous peak current is below the approved battery/regulator continuous and transient limits with design margin; no brownout or reset occurs. With the switch OFF, ESP32/LCD operation ceases and no new current temperature data is produced; stale values are marked unavailable remotely.

## Independent criteria source

The OFF behavior is explicit. Current margin is derived from selected component ratings and worst-case measured peaks; the design review must state the accepted margin.

## Test type and automation rationale

Automated instruments and a relay capture repeatable traces, but final hardware and safety supervision make the test semi-automated HIL.

## Required instrumentation and observability

Complete power schematic/BOM, add current shunt/analyzer channel, reset-reason telemetry, relay control, and a power-mode capture script.

## Evidence retained

Current/voltage waveforms, rating table, margin calculation, reset log, remote-data timeline.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
