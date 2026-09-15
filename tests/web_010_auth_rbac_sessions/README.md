<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# WEB-010: Authentication, server-side RBAC, password hashing, and session security

Primary type: Security integration test  
Execution mode: Automated  
Current feasibility: Blocked; web/auth/users table absent  
Scaffold status: harvested

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-SEC-MLR-750 | [SCRUM-609](https://pkamp.atlassian.net/browse/SCRUM-609) | SWE-SEC-MLR-750 - Web Authentication and Authorization |
| SWE-SEC-LLR-750 | [SCRUM-625](https://pkamp.atlassian.net/browse/SCRUM-625) | SWE-SEC-LLR-750 - Password Hashing |
| SWE-SEC-LLR-751 | [SCRUM-626](https://pkamp.atlassian.net/browse/SCRUM-626) | SWE-SEC-LLR-751 - Authenticated Session |
| SWE-SEC-LLR-752 | [SCRUM-627](https://pkamp.atlassian.net/browse/SCRUM-627) | SWE-SEC-LLR-752 - Server-Side Authorization |
| SWE-SEC-LLR-753 | [SCRUM-628](https://pkamp.atlassian.net/browse/SCRUM-628) | SWE-SEC-LLR-753 - Session Cookie Protection |

## Purpose and usefulness

Endpoint-by-role enumeration proves authorization at the trusted server boundary and detects UI-only protection.

## Profiles and qualification credit

- pr1-unit: automated; PARTIAL evidence; capabilities: python, pytest, jsonschema, node, npm, pr1-console.
- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, pr1-console, browser, scripted-source, implementation:WEB-010:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use USER, ADMIN, disabled user, unauthenticated client, production password hasher/session mode, TLS-like deployment configuration, and every privileged endpoint.

## Detailed repeatable procedure

1) Register/set known passwords and inspect stored hashes for salt/modern algorithm and no plaintext. 2) Authenticate valid/invalid/disabled users. 3) Call every control, recipient, rule, and account mutation endpoint as unauthenticated, USER, and ADMIN. 4) Bypass hidden UI by direct HTTP. 5) Inspect cookie flags if cookie sessions are used. 6) Replay/expire sessions. 7) Run dependency/security scanner and basic CSRF checks appropriate to the session design.

## PASS criteria

Only authenticated ADMIN requests can mutate privileged resources; USER can read allowed data but receives 403 on mutations and unauthenticated receives 401; disabled/expired sessions fail; passwords are uniquely salted modern hashes with no plaintext; cookie sessions are HttpOnly, appropriate SameSite, and Secure in TLS deployment.

## Independent criteria source

Roles and server-side enforcement are explicit. Cookie settings depend on deployment, so the test evaluates the approved environment-specific policy.

## Test type and automation rationale

Role matrices and security headers are automatable; periodic expert penetration review is supplemental.

## Required instrumentation and observability

Implement auth/users, modern hasher, centralized authorization middleware, endpoint inventory test, session policy, CSRF controls, and security scans.

## Evidence retained

Role/endpoint matrix, redacted user rows, hash metadata, response codes, cookie/header capture, scanner report.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
