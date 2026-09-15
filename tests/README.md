# Thermometer requirement test runner

This directory implements Phases 0–2 of the project test architecture. It freezes the 255-requirement Jira baseline and 56-row test matrix, validates one primary test owner per requirement, plans capability-aware runs, executes one consolidated test at a time, and publishes hash-indexed evidence.

The runner wraps each component's native tools. It does not translate the connector tests, ESP-IDF build, or PR #1 Vitest suite into a second implementation.

## Setup

From the repository root, activate the backend virtual environment and install development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\pc_client\requirements-dev.txt
```

ESP-IDF tests additionally require an initialized ESP-IDF terminal so `idf.py` is on `PATH`. PR #1 unit tests become available after its `package.json`, `src/`, and `server/` trees are integrated and `npm install` has been run.

## Commands

```powershell
python -m tests.runner list
python -m tests.runner validate
python -m tests.runner plan --profile unit --all
python -m tests.runner plan --profile unit --changed-component backend --credit FULL --all
python -m tests.runner run --profile unit --test BLE-005 --executor "Your Name"
python -m tests.runner report --run <run-id>
```

`plan` is read-only: it starts no services and flashes no firmware. Selection
can be narrowed by test ID, group, Jira key, requirement UID, feasibility,
changed component, or the requested profile's evidence-credit level. Phase 1
intentionally supports one `--test` per `run`; parallel scheduling comes after
the single-test lifecycle is stable.

Results are written under `tests/results/<run-id>/` and are ignored by Git. `result.json` is authoritative; `result.md` and `summary.csv` are generated views. `PASS` is separate from evidence credit, and only `PASS + FULL` closes formal requirement coverage.

PR #1 profiles must identify the exact reviewed source:

```powershell
python -m tests.runner run --profile pr1-unit --test WEB-001 --executor "Your Name" --source-kind pr --pr-number 1 --pr-head-sha 85b16b47e038c4fe74cf5998a4692f06ee321b0c
```

Use `--source-kind integration --integration-sha <sha>` after a reproducible
merge or rebase. The runner never labels a PR-head result as main-branch
evidence.

## Frozen inputs

- `requirements.lock.json`: read-only Jira export with content hashes and primary owners.
- `test_matrix.lock.csv`: the supplied 56-row procedure and traceability matrix.
- `input_baseline.json`: immutable hashes/counts for the reviewed matrix and Jira export.
- `source_baseline.json`: reviewed main and GitHub PR #1 revisions.
- `_shared/existing_python_tests.json`: exact one-owner mapping for the 77 pre-runner connector tests.

Changing a requirement, mapping, or existing test case makes `validate` fail until the corresponding baseline is deliberately reviewed and regenerated.

## Qualification gates

The runner records regression evidence but does not grant full closure while
any controlling item below is unresolved or lacks an approved deviation:

- Jira MySQL `control_commands` queue versus the current localhost REST path.
- Fixed 10–50 °C graph axes versus any optional extended/scrollable range.
- Persisted device identity, sample uniqueness, and one shared status vocabulary.
- Current-data freshness and physical-power versus connector-unavailable semantics.
- Numeric values for requirement placeholders written as `[N]`.
- Final sensor, LCD, backlight, USB-C, battery, enclosure, and acceptance fixtures.
- Durable alert idempotency, authenticated user/admin RBAC, providers, and evidence retention.

These are visible as missing capabilities or profile limitations. They must not
be changed into assumptions merely to obtain a green test result.
