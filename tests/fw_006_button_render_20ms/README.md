<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-006: Physical sensor buttons and cached render within 20 ms

Primary type: Firmware HIL timing  
Execution mode: Semi-automated  
Current feasibility: Blocked by physical input and LCD drivers  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-307 | [SCRUM-463](https://pkamp.atlassian.net/browse/SCRUM-463) | SWE-EMB-MLR-307 - Local Display Response Time |
| SWE-EMB-LLR-312 | [SCRUM-482](https://pkamp.atlassian.net/browse/SCRUM-482) | SWE-EMB-LLR-312 - Physical Button Toggle |
| SWE-EMB-LLR-313 | [SCRUM-483](https://pkamp.atlassian.net/browse/SCRUM-483) | SWE-EMB-LLR-313 - Disconnected Button Behavior |
| SWE-EMB-LLR-316 | [SCRUM-486](https://pkamp.atlassian.net/browse/SCRUM-486) | SWE-EMB-LLR-316 - Cached Display Data |
| SWE-EMB-LLR-317 | [SCRUM-487](https://pkamp.atlassian.net/browse/SCRUM-487) | SWE-EMB-LLR-317 - Button-to-Render Scheduling |

## Purpose and usefulness

Timing from the real input edge through rendering is the useful requirement; a function-call unit test would omit debounce and scheduling.

## Profiles and qualification credit

- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, verification-firmware, implementation:FW-006:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use production buttons, debounce configuration, LCD, logic analyzer, and a way to pause sensor conversion so cached-value behavior is observable.

## Detailed repeatable procedure

1) Establish valid cached values. 2) Trigger one debounced Sensor 1 press and measure input-handler event to completed LCD update. 3) Repeat Sensor 2. 4) Run ten accepted presses per button and several sub-debounce pulses. 5) Pause an in-progress sensor conversion during a press. 6) Disconnect a sensor and press its button. 7) Verify only the selected connected sensor toggles.

## PASS criteria

Every accepted press updates from cached data and completes the firmware scheduling/render path within 20.0 ms; bounce pulses create exactly one transition; the other sensor is unchanged; conversion completion is not awaited; and a disconnected-sensor press cannot expose a numeric value or leave DISCONNECTED.

## Independent criteria source

The 20 ms criterion is explicit. Debounce pulse widths come from the selected hardware configuration and must be baselined.

## Test type and automation rationale

Logic-analyzer automation calculates latency, while physical input/LCD make this HIL and require setup supervision.

## Required instrumentation and observability

Implement buttons/debounce and real LCD; add GPIO test point, render-complete signal, high-resolution timestamps, and controllable slow sensor backend.

## Evidence retained

Logic traces, per-trial latency table, bounce vectors, state logs, LCD capture.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
