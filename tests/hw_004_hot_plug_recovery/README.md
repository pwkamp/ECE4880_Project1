<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-004: Powered hot-plug and automatic sensor recovery

Primary type: Hardware-in-the-loop fault injection  
Execution mode: Semi-automated  
Current feasibility: Blocked by real sensor hardware/driver  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-210 | [SCRUM-406](https://pkamp.atlassian.net/browse/SCRUM-406) | SYS-HLR-210 - Sensor Hot-Plug Recovery |
| HWE-MLR-204 | [SCRUM-425](https://pkamp.atlassian.net/browse/SCRUM-425) | HWE-MLR-204 - Hot-Plug Electrical Protection |
| HWE-LLR-206 | [SCRUM-440](https://pkamp.atlassian.net/browse/SCRUM-440) | HWE-LLR-206 - Hot-Plug Input Protection |

## Purpose and usefulness

The test creates the actual electrical transient and observes the specified software recovery, which neither a static review nor a mocked disconnect alone can prove.

## Profiles and qualification credit

- hil-physical: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, real-sensors, sensor-switching, esp32, implementation:HW-004:hil-physical.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Run the production sensor interface and firmware while logging power rails, resets, sensor states, sample sequences, and BLE current data.

## Detailed repeatable procedure

1) Establish valid readings from both sensors. 2) Remove Sensor 1 while powered, wait five sample periods, and reconnect it; repeat for Sensor 2. 3) Repeat ten cycles per port. 4) During one cycle remove/reconnect while history is being read. 5) Confirm the unaffected sensor continues sampling. 6) Inspect for reset/brownout and excessive insertion transient. 7) After the final cycle compare readings to the reference.

## PASS criteria

No cycle damages hardware, resets the ESP32, or blocks the other sensor. The removed sensor becomes DISCONNECTED with no numeric current value, automatically resumes on the first configured valid read after reconnection, and returns with display state OFF without user intervention.

## Independent criteria source

Ten cycles provide a repeatable transient screen. State behavior uses the current configured one failed/one successful read criteria and exact Jira recovery semantics.

## Test type and automation rationale

Relay-assisted plug simulation and log assertions make the repeated HIL sequence objective; physical setup and safety checks remain manual.

## Required instrumentation and observability

Implement real sensor backend; add reset-reason logging, rail/current capture, per-sensor fault injection or break-out relays, and correlated sample/state logs.

## Evidence retained

Rail trace, reset counters, sensor/BLE logs, per-cycle result table, post-test readings and inspection.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
