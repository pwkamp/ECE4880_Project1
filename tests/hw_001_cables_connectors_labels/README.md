<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# HW-001: Sensor cables, supported connectors, strain relief, and port identity

Primary type: Full-hardware inspection and measurement  
Execution mode: Manual  
Current feasibility: Blocked; hardware directory is a placeholder  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| HWE-MLR-200 | [SCRUM-421](https://pkamp.atlassian.net/browse/SCRUM-421) | HWE-MLR-200 - Sensor Quantity and Cable Length |
| HWE-MLR-209 | [SCRUM-430](https://pkamp.atlassian.net/browse/SCRUM-430) | HWE-MLR-209 - USB-C Sensor Connections |
| HWE-LLR-200 | [SCRUM-434](https://pkamp.atlassian.net/browse/SCRUM-434) | HWE-LLR-200 - Cable Length Verification |
| HWE-LLR-204 | [SCRUM-438](https://pkamp.atlassian.net/browse/SCRUM-438) | HWE-LLR-204 - Panel Connector Support |
| HWE-LLR-205 | [SCRUM-439](https://pkamp.atlassian.net/browse/SCRUM-439) | HWE-LLR-205 - Cable Strain Relief |
| HWE-LLR-214 | [SCRUM-448](https://pkamp.atlassian.net/browse/SCRUM-448) | HWE-LLR-214 - Sensor 1 USB-C Port |
| HWE-LLR-215 | [SCRUM-449](https://pkamp.atlassian.net/browse/SCRUM-449) | HWE-LLR-215 - Sensor 2 USB-C Port |
| HWE-LLR-216 | [SCRUM-450](https://pkamp.atlassian.net/browse/SCRUM-450) | HWE-LLR-216 - Port Identification |

## Purpose and usefulness

These related features share the same physical assemblies and inspection setup, so one controlled first-article inspection is useful and avoids redundant handling.

## Profiles and qualification credit

- full-hardware: manual; PARTIAL evidence; capabilities: python, pytest, jsonschema, final-hardware, measurement-tools, human-review, implementation:HW-001:full-hardware.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use two completed sensor assemblies, third-box enclosure, calibrated tape/ruler, approved drawings, and an inspection checklist.

## Detailed repeatable procedure

1) Measure from each third-box connector interface to its sensing element with the cable straight and unstretched. 2) Record photographs of each measurement. 3) Inspect panel support so solder joints are not the primary mechanical retention. 4) Inspect strain relief at probe and connector ends. 5) Mate/unmate each casual-user connector five times. 6) Verify dedicated USB-C pairs and permanent visual differentiation for Sensor 1 and Sensor 2. 7) Cross-check wiring and labels against drawings.

## PASS criteria

Each cable is 0.90 m to 1.10 m; both external connectors are mechanically supported independently of PCB solder joints; both cable ends have strain relief; five connect/disconnect cycles cause no damage; and Sensor 1 versus Sensor 2 ports are permanent and unambiguous.

## Independent criteria source

The length band is the exact 1.0 +/-0.1 m requirement. Five mating cycles are a limited workmanship screen, not a lifetime claim.

## Test type and automation rationale

Dimensions, retention, and label clarity are physical properties that require manual inspection; measurement capture can be templated but not fully simulated.

## Required instrumentation and observability

Add released drawings, cable/connector part numbers, assembly serial numbers, inspection form, and photo naming convention.

## Evidence retained

Completed checklist, calibrated-tool ID, dimensions, photos, drawing revision, deviations.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
