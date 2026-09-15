<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# SYS-004: Configurable high/low email and SMS delivery

Primary type: Full-system external-service acceptance  
Execution mode: Semi-automated  
Current feasibility: Blocked by database, web settings, alert evaluator, and providers  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SYS-HLR-700 | [SCRUM-418](https://pkamp.atlassian.net/browse/SCRUM-418) | SYS-HLR-700 - Temperature Alerting |

## Purpose and usefulness

This proves the stakeholder-visible outcome, configuration independence, and valid-data guard rather than merely exercising an SDK call.

## Profiles and qualification credit

- external: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, mysql, web-console, email-sandbox, sms-sandbox, implementation:SYS-004:external.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use provider sandbox/test accounts for both email and SMS, multiple destinations, valid Sensor 1/Sensor 2 samples, and configurable minimum/maximum thresholds/messages.

## Detailed repeatable procedure

1) Configure at least two email and two SMS destinations with different thresholds/messages. 2) Hold all sources in range and confirm no delivery. 3) Drive one valid source above its maximum, then back to normal, then below its minimum. 4) Repeat for the other sensor and, if supported, Average. 5) Make a source invalid while numerically out of range. 6) Record provider acceptance and inbox/handset receipt. 7) Confirm the third box sends no notification itself.

## PASS criteria

Every enabled matching recipient receives exactly one configured message on each high or low episode; nonmatching recipients and invalid samples produce none; delivery is initiated by the computer through the configured provider; and one provider failure does not stop temperature polling.

## Independent criteria source

High/low, email/SMS, multiple destinations, and computer-originated delivery come directly from Jira. Exact provider latency is not specified, so PASS is based on accepted and received delivery, not an invented deadline.

## Test type and automation rationale

External services and actual receipt require semi-automated acceptance: automated orchestration plus human/provider receipt evidence.

## Required instrumentation and observability

Implement alert tables/UI/evaluator/provider adapters; add sandbox credentials, provider request IDs, idempotency keys, and test inbox/SMS capture.

## Evidence retained

Configuration export, input samples, evaluator transitions, provider request/response IDs, receipt evidence, polling continuity log.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
