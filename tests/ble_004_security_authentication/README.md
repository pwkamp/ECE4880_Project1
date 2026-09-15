<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# BLE-004: BLE bonding, encrypted access, and application authentication

Primary type: Security HIL  
Execution mode: Semi-automated  
Current feasibility: Partially runnable with current pairing/auth code  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| INT-MLR-406 | [SCRUM-505](https://pkamp.atlassian.net/browse/SCRUM-505) | INT-MLR-406 - BLE Access Control |
| INT-LLR-414 | [SCRUM-521](https://pkamp.atlassian.net/browse/SCRUM-521) | INT-LLR-414 - BLE Pairing/Bonding |

## Purpose and usefulness

The attack-oriented sequence proves both BLE-layer and application-layer controls and their lifecycle, not just successful pairing.

## Profiles and qualification credit

- unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema.
- hil-sim: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, esp32, ble, verification-firmware, implementation:BLE-004:hil-sim.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use the production ESP32, Windows central, second unauthorized central, unique six-digit credential including a leading-zero case, packet capture, and controllable clocks.

## Detailed repeatable procedure

1) Attempt protected GET_CURRENT and SET_DISPLAY without bonding and without application proof. 2) Enroll through Windows Provide PIN and verify EncryptionAndAuthentication. 3) Complete AUTH_BEGIN/AUTH_PROVE and access protected operations. 4) Verify the raw passkey never appears in application packets/logs. 5) Replay a nonce and use an expired nonce after five seconds. 6) submit three bad proofs and verify 30-second lockout. 7) Disconnect and confirm application auth clears. 8) Test authenticated reset and unauthorized reset.

## PASS criteria

Unauthenticated operations are rejected and cause no state change; the authenticated bond plus fresh valid proof succeeds; nonce is 16 bytes, single use, and expires at five seconds; three failures lock authentication for 30 seconds; disconnect clears session auth; only authenticated reset removes the owner bond; no raw passkey is exposed.

## Independent criteria source

Five seconds, three failures, 30-second lockout, 16-byte nonce, and six-digit provisioning come from the released configuration and Jira security requirements.

## Test type and automation rationale

Cryptographic vector parts are automated; real Windows/ESP32 bonding and a second central require HIL.

## Required instrumentation and observability

Add repeatable Windows pairing fixture, unauthorized central, secret-redacting log assertions, auth event audit, and packet-capture decoder.

## Evidence retained

Bond properties, packets, auth event timeline, negative statuses, redacted logs, reset result.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
