<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->
# DB-003: Users, roles, recipients, and alert-rule schema

Primary type: MySQL schema and CRUD integration  
Execution mode: Automated  
Current feasibility: Blocked; tables are absent  
Scaffold status: placeholder

## Requirements

| UID | Jira | Approved baseline summary |
|---|---|---|
| SWE-DB-MLR-552 | [SCRUM-532](https://pkamp.atlassian.net/browse/SCRUM-532) | SWE-DB-MLR-552 - Configuration and Authorization Storage |
| SWE-DB-LLR-554 | [SCRUM-554](https://pkamp.atlassian.net/browse/SCRUM-554) | SWE-DB-LLR-554 - users Table |
| SWE-DB-LLR-555 | [SCRUM-555](https://pkamp.atlassian.net/browse/SCRUM-555) | SWE-DB-LLR-555 - alert_recipients Table |
| SWE-DB-LLR-556 | [SCRUM-556](https://pkamp.atlassian.net/browse/SCRUM-556) | SWE-DB-LLR-556 - alert_rules Table |

## Purpose and usefulness

Production CRUD round trips verify durable application behavior and database constraints together.

## Profiles and qualification credit

- sitl: automated; FULL evidence; capabilities: python, pytest, jsonschema, mysql-test-instance, production-mysql-adapter, implementation:DB-003:sitl.

A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.

## Preconditions and setup

Use ephemeral MySQL, migrations, password hasher, and repository/ORM models for users, recipients, rules, and rule-recipient links.

## Detailed repeatable procedure

1) Create USER and ADMIN accounts and attempt an invalid role. 2) Inspect stored password fields and audit timestamps. 3) Insert multiple EMAIL and SMS recipients. 4) Create rules with independent min/max Celsius thresholds, monitored source, high/low messages, enabled state, and recipient links. 5) Update/disable/delete records through production repository methods. 6) Restart the application and read them back. 7) Test uniqueness and referential integrity.

## PASS criteria

All tables/relationships exist and persist across restart; usernames are unique; roles accept only USER/ADMIN; no plaintext password field/value exists; multiple recipients of each type persist; every rule retains both thresholds, messages, source, and linked recipients; invalid enums/orphans are rejected.

## Independent criteria source

Fields/enums are explicit Jira requirements. Persistence across restart distinguishes real database storage from in-memory mocks.

## Test type and automation rationale

Isolated database fixtures make this fully automated.

## Required instrumentation and observability

Add migrations/models/repositories for users, recipients, rules, link table, hashes and audit timestamps; add seed factory.

## Evidence retained

Schema snapshot, CRUD transcript, restart readback, constraint-negative results, redacted rows.

## Safety, cleanup, and known limitations

The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.
