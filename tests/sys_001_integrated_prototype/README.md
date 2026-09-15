<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# SYS-001: Integrated prototype, internet data access, and 300-second graph

Primary type: Full-system acceptance  
Execution mode: Semi-automated  
Current feasibility: Blocked by final hardware, database, and web UI  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| PRJ-REQ-002 | [SCRUM-400](https://pkamp.atlassian.net/browse/SCRUM-400) | PRJ-REQ-002 - Functional Prototype |
| SYS-HLR-100 | [SCRUM-403](https://pkamp.atlassian.net/browse/SCRUM-403) | SYS-HLR-100 - System Composition |
| SYS-HLR-110 | [SCRUM-404](https://pkamp.atlassian.net/browse/SCRUM-404) | SYS-HLR-110 - Internet-Accessible Temperature Data |
| SYS-HLR-500 | [SCRUM-414](https://pkamp.atlassian.net/browse/SCRUM-414) | SYS-HLR-500 - Remote Real-Time Display |
| SYS-HLR-600 | [SCRUM-417](https://pkamp.atlassian.net/browse/SCRUM-417) | SYS-HLR-600 - Historical Temperature Graph |

## Purpose and usefulness

This single acceptance scenario efficiently proves the coherent data path and prototype composition while lower-level tests isolate failures.

## Profiles and qualification credit

- full-hardware: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, full-system-bench, mysql, web-console, implementation:SYS-001:full-hardware.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Assemble the computer, two sensor assemblies, battery third box, BLE connector, MySQL adapter/database, web server/UI, and networked receiving browser. Preload or collect at least 300 seconds of data.

## Detailed repeatable procedure

1) Record build IDs and start all components. 2) Verify the system contains the required computer, two probes, battery third box, and notification-capable computer path. 3) From a second networked device, open the web application. 4) Observe Sensor 1, Sensor 2, average, and statuses for 60 seconds while applying distinguishable temperatures to the probes. 5) Open the compliance graph and let it run through a 300-second window. 6) Briefly interrupt one probe and confirm the remote status changes. 7) Save API/DB timestamps, BLE logs, screenshots, and graph data.

## PASS criteria

The remote browser is usable over the intended internet-connected deployment path; both sensor values and statuses track the physical stimuli; the graph contains the latest 300 one-second positions with missing data represented distinctly; and all required components remain operational for the run.

## Independent criteria source

The 300-second window and two-sensor/average/status content are specified by Jira. No additional accuracy limit is added here because HW-002 owns accuracy.

## Test type and automation rationale

Automation should drive stimuli/log collection and compare data; a human confirms the assembled prototype and readable UI because physical composition and usability are observable properties.

## Required instrumentation and observability

Implement the concrete database adapter, web current/history APIs and UI, deployment/network fixture, synchronized test-run IDs, and reference-probe logging.

## Evidence retained

Assembly photos, version manifest, network diagram, timestamped DB/API/BLE logs, exported graph data, screenshots, result JSON.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
