<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-002: Sensor immersion, range, and room/ice accuracy qualification

Primary type: Full-hardware environmental measurement  
Execution mode: Semi-automated  
Current feasibility: Blocked; sensor selection and real driver are absent  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-320 | [SCRUM-410](https://pkamp.atlassian.net/browse/SCRUM-410) | SYS-HLR-320 - Temperature Accuracy |
| SYS-HLR-321 | [SCRUM-419](https://pkamp.atlassian.net/browse/SCRUM-419) | SYS-HLR-321 - Room-Temperature Accuracy |
| SYS-HLR-322 | [SCRUM-420](https://pkamp.atlassian.net/browse/SCRUM-420) | SYS-HLR-322 - Ice-Water Accuracy |
| HWE-MLR-201 | [SCRUM-422](https://pkamp.atlassian.net/browse/SCRUM-422) | HWE-MLR-201 - Sensor Mechanical Robustness |
| HWE-MLR-212 | [SCRUM-433](https://pkamp.atlassian.net/browse/SCRUM-433) | HWE-MLR-212 - Sensor/Signal-Chain Capability |
| HWE-LLR-201 | [SCRUM-435](https://pkamp.atlassian.net/browse/SCRUM-435) | HWE-LLR-201 - Wet Sensor Construction |
| HWE-LLR-220 | [SCRUM-454](https://pkamp.atlassian.net/browse/SCRUM-454) | HWE-LLR-220 - Sensor Range Selection |
| HWE-LLR-221 | [SCRUM-455](https://pkamp.atlassian.net/browse/SCRUM-455) | HWE-LLR-221 - Accuracy Budget |

## Purpose and usefulness

One qualification sequence uses the same calibrated setup to prove immersion suitability, endpoint accuracy, and post-immersion function without unrelated stress tests.

## Profiles and qualification credit

- full-hardware: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, final-hardware, reference-thermometer, implementation:HW-002:full-hardware.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use both production sensors, calibrated reference thermometer, stirred ice-water bath, stable laboratory room, data logger, timer, datasheets, and sealed probe assemblies.

## Detailed repeatable procedure

1) Review the sensor datasheet range and accuracy. 2) Stabilize the reference near laboratory room temperature and log both sensors for 60 seconds. 3) Immerse only the intended probe/cable region in a stirred water-ice mixture without stressing the connector; stabilize and log 60 seconds. 4) Remove, dry, inspect for water ingress, and retest at room temperature. 5) Compute mean, maximum absolute error, and pre/post drift for each sensor. 6) Compare measured results with the end-to-end error budget.

## PASS criteria

Datasheet range includes -10 C through +63 C. At room conditions each reported value is 22 C +/-4 C when the reference is approximately 22 C; in ice water each is 0 C +/-2 C. There is no damage, leakage, intermittent behavior, or material post-test drift, and the error budget preserves the stated limits.

## Independent criteria source

The range and tolerance values are explicit Jira criteria. Sixty-second stabilized windows provide repeatable averages while retaining all samples for review.

## Test type and automation rationale

Scripts should collect and calculate results, while a person performs safe immersion and inspects the assembly, making semi-automated full-hardware testing appropriate.

## Required instrumentation and observability

Select sensors and encapsulation, implement real drivers, add reference-probe acquisition, calibration metadata, and a reusable analysis script.

## Evidence retained

Datasheets, calibration certificates, raw 1 Hz logs, bath photos, error calculations, inspection photos.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
