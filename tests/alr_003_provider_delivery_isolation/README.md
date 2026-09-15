<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# ALR-003: Email/SMS provider adapters and failure isolation

Primary type: Provider sandbox integration  
Execution mode: Semi-automated  
Current feasibility: Blocked; adapters absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-ALR-MLR-703 | [SCRUM-606](https://pkamp.atlassian.net/browse/SCRUM-606) | SWE-ALR-MLR-703 - Third-Party Notification Adapters |
| SWE-ALR-LLR-706 | [SCRUM-616](https://pkamp.atlassian.net/browse/SCRUM-616) | SWE-ALR-LLR-706 - SMS Provider Adapter |
| SWE-ALR-LLR-707 | [SCRUM-617](https://pkamp.atlassian.net/browse/SCRUM-617) | SWE-ALR-LLR-707 - Email Provider Adapter |
| SWE-ALR-LLR-708 | [SCRUM-618](https://pkamp.atlassian.net/browse/SCRUM-618) | SWE-ALR-LLR-708 - Provider Failure Handling |

## Purpose and usefulness

The test verifies the real integration boundary and the critical isolation property, not just local message construction.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- external: semi-automated; FULL evidence; capabilities: python, pytest, jsonschema, email-sandbox, sms-sandbox, provider-adapters, implementation:ALR-003:external.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use provider sandbox/test inbox and SMS capture, externally supplied credentials, provider spies for deterministic faults, and active 1 Hz polling.

## Detailed repeatable procedure

1) Send known text to one email and one SMS destination through their adapters. 2) Verify destination/message preservation and provider request IDs. 3) Repeat for multiple destinations. 4) Inject timeout, rate limit, authentication failure, and 5xx in each provider. 5) Observe recorded/logged failure and continue subsequent recipients. 6) Verify the next one-second temperature poll/evaluation occurs on schedule. 7) scan source/logs for credentials.

## PASS criteria

Both adapters call the configured third-party API with correct destination/text and receive sandbox acceptance/receipt; every failure is observable, does not expose credentials, does not block later recipients, and does not delay/terminate the one-second temperature loop.

## Independent criteria source

No alert delivery deadline is specified. Correct accepted/received delivery plus uninterrupted 1 Hz operation is the useful criterion.

## Test type and automation rationale

Provider sandboxes and fault proxies support automation, while final receipt inspection makes release execution semi-automated.

## Required instrumentation and observability

Implement adapters, external secrets, timeouts/retries/idempotency, provider request logging/redaction, fault proxy, and test inbox/SMS capture.

## Evidence retained

Provider requests/responses, receipt capture, injected-failure log, poll timing, secret-scan report.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
