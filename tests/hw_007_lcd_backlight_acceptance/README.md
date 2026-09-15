<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-007: LCD content capacity, readability, states, and local backlight control

Primary type: Full-hardware HITL display acceptance  
Execution mode: Semi-automated  
Current feasibility: Blocked by LCD/backlight/input selection and real drivers  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-400 | [SCRUM-411](https://pkamp.atlassian.net/browse/SCRUM-411) | SYS-HLR-400 - Local Temperature Display and Controls |
| SYS-HLR-410 | [SCRUM-412](https://pkamp.atlassian.net/browse/SCRUM-412) | SYS-HLR-410 - Local Display Performance |
| SYS-HLR-420 | [SCRUM-413](https://pkamp.atlassian.net/browse/SCRUM-413) | SYS-HLR-420 - Local Sensor Fault Indication |
| HWE-MLR-207 | [SCRUM-428](https://pkamp.atlassian.net/browse/SCRUM-428) | HWE-MLR-207 - Character LCD |
| HWE-MLR-208 | [SCRUM-429](https://pkamp.atlassian.net/browse/SCRUM-429) | HWE-MLR-208 - Physical Backlight Control |
| HWE-MLR-211 | [SCRUM-432](https://pkamp.atlassian.net/browse/SCRUM-432) | HWE-MLR-211 - Display Character Capability |
| HWE-MLR-213 | [SCRUM-634](https://pkamp.atlassian.net/browse/SCRUM-634) | HWE-MLR-213 - Indoor LCD Readability |
| HWE-MLR-214 | [SCRUM-635](https://pkamp.atlassian.net/browse/SCRUM-635) | HWE-MLR-214 - Display Size and Resolution Unconstrained |
| HWE-LLR-210 | [SCRUM-444](https://pkamp.atlassian.net/browse/SCRUM-444) | HWE-LLR-210 - LCD Electrical Interface |
| HWE-LLR-211 | [SCRUM-445](https://pkamp.atlassian.net/browse/SCRUM-445) | HWE-LLR-211 - Variable Backlight Drive |
| HWE-LLR-212 | [SCRUM-446](https://pkamp.atlassian.net/browse/SCRUM-446) | HWE-LLR-212 - Backlight Control Input - Button Option |
| HWE-LLR-213 | [SCRUM-447](https://pkamp.atlassian.net/browse/SCRUM-447) | HWE-LLR-213 - Backlight Control Input - Potentiometer Option |
| HWE-LLR-219 | [SCRUM-453](https://pkamp.atlassian.net/browse/SCRUM-453) | HWE-LLR-219 - LCD Signed Temperature Support |
| HWE-LLR-222 | [SCRUM-638](https://pkamp.atlassian.net/browse/SCRUM-638) | HWE-LLR-222 - Indoor Readability Verification |

## Purpose and usefulness

The related requirements concern what the same local display assembly can show and how a local user perceives/adjusts it, so one state matrix avoids repetitive setups.

## Profiles and qualification credit

- full-hardware: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, lcd, backlight-input, camera, human-review, implementation:HW-007:full-hardware.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use the production LCD, enclosure, selected button or potentiometer, normal indoor lighting, intended orientation/viewing distance, both sensors, luminance meter if available, and a camera.

## Detailed repeatable procedure

1) Render Sensor 1 and Sensor 2 ON, OFF, and DISCONNECTED states; render valid negative and +63 C values and the two-sensor average. 2) Confirm labels and signed values fit without ambiguous truncation. 3) Evaluate at the approved normal laboratory distance and indoor light level. 4) Exercise the chosen backlight input across its full travel/sequence. 5) Record at least low, medium, and high output and verify current rating. 6) Disconnect each sensor and confirm an error label replaces its number. 7) Have two reviewers repeat the readability check.

## PASS criteria

All required labels, OFF/DISCONNECTED/error text, signed -10 through +63 C values, and average render correctly. Both reviewers can read every state at the intended distance/orientation. The chosen input yields at least three discernible brightness levels, remains within the LCD current rating, and does not change sensor acquisition.

## Independent criteria source

Exact content/range and at least low/medium/high come from Jira. Lighting distance and luminance should be baselined from the actual lab because Jira says normal conditions rather than a numeric lux value.

## Test type and automation rationale

Automated state injection and image capture improve repeatability; human judgment is still necessary for readability and discernible brightness.

## Required instrumentation and observability

Select LCD geometry/bus and input option; implement real display/local-control drivers; add display-state injection, PWM/ADC telemetry, current measurement, and a signed readability fixture.

## Evidence retained

State matrix, photos, reviewer records, lux/distance, brightness/current measurements, firmware revision.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
