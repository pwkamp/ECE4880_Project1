<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# FW-007: Backlight software abstraction and selected input behavior

Primary type: Firmware unit plus HIL  
Execution mode: Semi-automated  
Current feasibility: Blocked by backlight hardware/input selection  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-EMB-MLR-309 | [SCRUM-465](https://pkamp.atlassian.net/browse/SCRUM-465) | SWE-EMB-MLR-309 - Backlight Brightness Control |
| SWE-EMB-LLR-320 | [SCRUM-490](https://pkamp.atlassian.net/browse/SCRUM-490) | SWE-EMB-LLR-320 - Backlight Abstraction |
| SWE-EMB-LLR-321 | [SCRUM-491](https://pkamp.atlassian.net/browse/SCRUM-491) | SWE-EMB-LLR-321 - Button Backlight Algorithm |
| SWE-EMB-LLR-322 | [SCRUM-492](https://pkamp.atlassian.net/browse/SCRUM-492) | SWE-EMB-LLR-322 - Potentiometer Backlight Algorithm |

## Purpose and usefulness

One parameterized test covers the common abstraction and branches only into the actually selected physical option.

## Profiles and qualification credit

- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, verification-firmware, implementation:FW-007:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use the normalized backlight API, mock driver, and selected button or potentiometer hardware.

## Detailed repeatable procedure

1) Call normalized brightness at 0, low, medium, high, 100, and invalid values. 2) Verify rendering logic is independent from physical input logic. 3) If button selected, inject debounced presses and verify a finite cycle containing low, medium, and high. 4) If potentiometer selected, sweep usable ADC range, verify monotonic mapping, endpoints, and jitter suppression near boundaries. 5) Confirm PWM/current output tracks accepted changes.

## PASS criteria

The public function accepts the documented normalized range and applies safe clamping/rejection; selected input produces stable requested levels; button cycle contains at least low/medium/high or ADC maps the full usable range without chatter; display rendering remains independent.

## Independent criteria source

At least three button levels is explicit. ADC endpoints and jitter deadband must come from selected parts/noise measurements rather than an arbitrary number.

## Test type and automation rationale

Mapping and jitter logic are automatable; actual ADC/PWM behavior needs HIL.

## Required instrumentation and observability

Select input option; implement driver; publish normalized range, PWM/ADC telemetry, debounce/deadband constants, and unit/HIL hooks.

## Evidence retained

Unit vectors, ADC/PWM traces, level sequence, jitter test results.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
