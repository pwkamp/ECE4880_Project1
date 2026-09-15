<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-005: Local display content, average, fault text, and canonical Celsius

Primary type: Firmware unit plus HIL display  
Execution mode: Semi-automated  
Current feasibility: Partially runnable with LED; physical LCD missing  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-305 | [SCRUM-461](https://pkamp.atlassian.net/browse/SCRUM-461) | SWE-EMB-MLR-305 - Independent Local Display Control |
| SWE-EMB-MLR-306 | [SCRUM-462](https://pkamp.atlassian.net/browse/SCRUM-462) | SWE-EMB-MLR-306 - Local Average Display |
| SWE-EMB-MLR-308 | [SCRUM-464](https://pkamp.atlassian.net/browse/SCRUM-464) | SWE-EMB-MLR-308 - Local Fault Display |
| SWE-EMB-MLR-310 | [SCRUM-466](https://pkamp.atlassian.net/browse/SCRUM-466) | SWE-EMB-MLR-310 - Local Celsius Presentation |
| SWE-EMB-LLR-314 | [SCRUM-484](https://pkamp.atlassian.net/browse/SCRUM-484) | SWE-EMB-LLR-314 - Average Calculation |
| SWE-EMB-LLR-315 | [SCRUM-485](https://pkamp.atlassian.net/browse/SCRUM-485) | SWE-EMB-LLR-315 - Average Validity |
| SWE-EMB-LLR-318 | [SCRUM-488](https://pkamp.atlassian.net/browse/SCRUM-488) | SWE-EMB-LLR-318 - Disconnected LCD Text |
| SWE-EMB-LLR-319 | [SCRUM-489](https://pkamp.atlassian.net/browse/SCRUM-489) | SWE-EMB-LLR-319 - Off LCD Text |
| SWE-EMB-LLR-323 | [SCRUM-493](https://pkamp.atlassian.net/browse/SCRUM-493) | SWE-EMB-LLR-323 - Canonical Temperature Unit |

## Purpose and usefulness

A state-by-boundary matrix finds content and arithmetic defects that happy-path display screenshots miss.

## Profiles and qualification credit

- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, verification-firmware, implementation:FW-005:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use a mock display framebuffer and later the production LCD. Supply boundary temperatures, valid/invalid states, and all display-enable combinations.

## Detailed repeatable procedure

1) Exercise all nine ON/OFF/DISCONNECTED combinations for the two sensors. 2) Inject -10.00 C, 0.00 C, 22.00 C, and +63.00 C. 3) When both are valid/enabled, compare the displayed average with widened arithmetic. 4) Test near int16 extremes to detect addition overflow. 5) Verify average is absent unless both inputs are valid and enabled. 6) Verify faults show text, OFF shows the sensor-specific OFF label, and all payload/internal values remain Celsius. 7) Repeat representative states on the LCD.

## PASS criteria

Every state renders the correct sensor label and content; no invalid sensor renders a numeric value; average equals (S1+S2)/2 without overflow or avoidable rounding and appears only when both are valid/enabled; signed required-range values fit; internal and BLE values stay Celsius.

## Independent criteria source

State rules, Celsius, and required range are explicit. Exact formatting beyond fitting/readability is not invented.

## Test type and automation rationale

Framebuffer assertions should be automated; the physical LCD mapping is a smaller HIL confirmation.

## Required instrumentation and observability

Implement real LCD backend; add framebuffer abstraction/snapshot tests, boundary vectors, and display event capture.

## Evidence retained

Matrix result, expected/actual framebuffer text, arithmetic vectors, LCD photos.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
