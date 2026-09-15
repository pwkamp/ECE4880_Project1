<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# DB-005: Database secret externalization

Primary type: Static security and deployment smoke test  
Execution mode: Automated  
Current feasibility: Runnable now for current files; production adapter config pending  
Scaffold status: implemented

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-DB-LLR-561 | [SCRUM-561](https://pkamp.atlassian.net/browse/SCRUM-561) | SWE-DB-LLR-561 - Database Credentials |

## Purpose and usefulness

The test proves both absence from source and usability of the intended external configuration path.

## Profiles and qualification credit

- unit: automated; FULL evidence; capabilities: python, pytest, jsonschema.
- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use secret scanner, clean checkout, production configuration loader, ephemeral credentials, and captured application logs.

## Detailed repeatable procedure

1) Scan tracked files and Git history for database passwords, connection strings, API keys, and known test canaries. 2) Start the service without credentials and verify a safe actionable failure or explicit no-op mode. 3) Inject credentials through approved environment/secret store and connect. 4) Rotate the credential and reconnect without code change. 5) Inspect normal/error logs and generated files for secrets.

## PASS criteria

No live secret or plaintext credential is present in version control, artifacts, or logs; deployment succeeds using only external configuration; missing configuration fails safely/observably; and credential rotation needs no source change.

## Independent criteria source

The requirement is qualitative; zero detected secrets and successful external injection are unambiguous PASS criteria.

## Test type and automation rationale

Static scans and deployment smoke checks are repeatable and belong in CI/CD.

## Required instrumentation and observability

Implement production adapter configuration schema, secret-store integration, redaction tests, canary scanner, and documented rotation procedure.

## Evidence retained

Scanner report, redacted startup logs, connection result, rotation record.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
