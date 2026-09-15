<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# BLE-001: Custom GATT service and requester-only application traffic

Primary type: BLE protocol HIL conformance  
Execution mode: Semi-automated  
Current feasibility: Partially runnable with current firmware/client  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| INT-MLR-400 | [SCRUM-499](https://pkamp.atlassian.net/browse/SCRUM-499) | INT-MLR-400 - BLE Transport |
| INT-MLR-401 | [SCRUM-500](https://pkamp.atlassian.net/browse/SCRUM-500) | INT-MLR-401 - Request/Response Application Protocol |
| INT-LLR-400 | [SCRUM-507](https://pkamp.atlassian.net/browse/SCRUM-507) | INT-LLR-400 - Custom GATT Service |
| INT-LLR-401 | [SCRUM-508](https://pkamp.atlassian.net/browse/SCRUM-508) | INT-LLR-401 - No Application Notifications |

## Purpose and usefulness

Packet capture distinguishes genuinely requester-only behavior from a client that merely ignores notifications.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, ble, verification-firmware, implementation:BLE-001:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Flash the release build, use a BLE sniffer plus scripted central, and know the released service/characteristic UUIDs.

## Detailed repeatable procedure

1) Scan and identify the device by the custom 128-bit service UUID/name. 2) Discover services and confirm one thermometer application service with request and response characteristics. 3) Observe advertising and an idle connected session for at least 30 seconds. 4) Confirm there are no application notifications/indications carrying temperature/history. 5) Issue each read transaction through a computer-initiated request and correlate the response. 6) Attempt to subscribe if the characteristic exposes that capability.

## PASS criteria

The released UUIDs match protocol JSON; the computer can identify a compatible device; application temperature/history appears only after a central request; and no unsolicited application notification/indication is observed in the idle window.

## Independent criteria source

UUIDs and requester-only behavior are exact requirements. Thirty idle seconds is sufficient to cover many 1 Hz sample periods without claiming exhaustive RF absence.

## Test type and automation rationale

A scripted central automates transactions, but RF packet capture with real firmware makes this semi-automated HIL.

## Required instrumentation and observability

Add HIL central script, sniffer capture profile, UUID manifest check, and CI parser for notification/indication frames.

## Evidence retained

PCAP, GATT discovery dump, request/response correlation table, firmware/config hashes.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
