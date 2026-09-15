<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-009: Hand and soldering-iron thermal response

Primary type: Full-hardware dynamic response  
Execution mode: Semi-automated  
Current feasibility: Blocked by production sensors and driver  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-310 | [SCRUM-409](https://pkamp.atlassian.net/browse/SCRUM-409) | SYS-HLR-310 - Thermal Response |
| HWE-MLR-216 | [SCRUM-637](https://pkamp.atlassian.net/browse/SCRUM-637) | HWE-MLR-216 - Sensor Thermal Response Capability |
| HWE-LLR-224 | [SCRUM-640](https://pkamp.atlassian.net/browse/SCRUM-640) | HWE-LLR-224 - Hand-Heating Verification |
| HWE-LLR-225 | [SCRUM-641](https://pkamp.atlassian.net/browse/SCRUM-641) | HWE-LLR-225 - Soldering-Iron Response Verification |

## Purpose and usefulness

The test compares the two stakeholder stimuli on the same sensors and baseline, directly proving observable relative response rather than an arbitrary absolute heating target.

## Profiles and qualification credit

- full-hardware: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, real-sensors, reference-thermometer, thermal-fixture, implementation:HW-009:full-hardware.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use both production sensors, 1 Hz logger, reference probe, timer, controlled starting temperature, and a soldering iron with fixed safe geometry/temperature.

## Detailed repeatable procedure

1) Stabilize both sensors and record a 10-second baseline. 2) Hold Sensor 1 in a hand using the prescribed grip and log until a sustained increase is visible; repeat Sensor 2. 3) Return to baseline. 4) Position the soldering iron at the approved distance or brief contact method and duration; repeat both sensors. 5) Compute time to first increase greater than combined noise/quantization and initial slope. 6) Inspect for damage and repeat baseline.

## PASS criteria

Each sensor shows a sustained increasing reported temperature after a few seconds of hand heating. Each soldering-iron trial produces an earlier first increase and/or a larger initial slope than that sensor's hand trial, with no damage. The approved setup and raw data make the comparison repeatable.

## Independent criteria source

Jira intentionally uses qualitative terms. The preapproved noise threshold and geometry make those terms reproducible without inventing an absolute response time.

## Test type and automation rationale

Logging and analysis are automated; stimulus placement and safety supervision require a human.

## Required instrumentation and observability

Select sensors; baseline hand grip, iron temperature/distance/contact duration, and noise threshold; add synchronized 1 Hz/reference logging.

## Evidence retained

Raw logs, reference data, setup photos, threshold definition, time/slope calculations, post-test inspection.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
