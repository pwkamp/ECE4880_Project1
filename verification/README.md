# ECE4880 requirements verification

This directory implements the requirements-driven qualification framework. The authoritative requirement content was read from Jira project `SCRUM` through the Atlassian connector on 2026-09-22 and frozen in `requirements.yaml`. Ordinary test execution is intentionally offline and never needs Jira credentials.

The catalog contains exactly 255 Jira requirements and 36 consolidated tests. `tests.yaml` is the source of truth for requirement mappings, profiles, fixtures, instrumentation, entrypoints, pass policy, human intervention, and limitations. JSON syntax is used inside the `.yaml` files because JSON is a YAML 1.2 subset and can be parsed by a clean Python installation.

## One-time setup

Use the existing backend virtual environment (or install `backend/requirements.txt` into one), install frontend dependencies, and install Playwright's managed Chromium runtime:

```powershell
cd frontend
npm ci
npx playwright install chromium
python -m pip install -r ..\verification\requirements.txt
```

The `integration`, `hil`, and `full` profiles also require Docker for their isolated MySQL 8.4 checks. Firmware qualification discovers `idf.py` from PATH, `IDF_PATH`, VS Code ESP-IDF settings, or standard `C:\esp\<version>\esp-idf` installations. HIL/full runs automatically reuse or start the backend, MySQL, and frontend while preserving the existing database volume; pass `--no-start-services` when managing them separately. Automatically started services remain running for post-test inspection.

## Commands

Run from the repository root:

```powershell
python verification/runner.py preflight software
python verification/runner.py run software
python verification/runner.py run integration
python verification/runner.py run hil
python verification/runner.py run full
python verification/runner.py run full --defer-photos

# Create a new run while importing unchanged conclusive results and evidence.
python verification/runner.py run full --resume-from latest --defer-photos

# Or select a specific recent run.
python verification/runner.py run full --resume-from 2026-09-23T042948Z_a106867

# Attach required photographs after a deferred run.
python verification/runner.py evidence add latest HW-01 --photo C:\evidence\box.jpg --complete

python verification/runner.py status
python verification/runner.py report latest
python verification/runner.py dashboard

# Record a traceable decision for a manual/semi-automated result.
python verification/runner.py adjudicate latest HW-02 BLOCKED --operator "Peter" --reason "Drop test fixture unavailable"

# Generate Markdown/LaTeX, optionally compile PDF, or add requirement pages.
python verification/generate_report.py latest
python verification/generate_report.py latest --pdf
python verification/generate_report.py latest --include-requirement-pages
```

`software` and `integration` never prompt for physical actions. HIL/full tests are ordered by the compatible power, BLE, and UART setup declared in `setup_groups.yaml`. The runner prints the complete checklist and affected test IDs, then pauses once before each physical setup change—even if a future automated test is assigned to that section. HIL workflows use numbered choices, prompt only for necessary physical actions, and automatically capture backend status plus MySQL-backed sample timelines. An unconnected third box fails the affected assisted test after the connection prompt. Use `--non-interactive` to record operator-dependent sections as `BLOCKED` instead of prompting:

```powershell
python verification/runner.py run full --non-interactive
```

`--resume-from` always creates a separate run folder. It reuses only `PASS`, `PASS_OVERRIDE`, and `NOT_APPLICABLE` results whose complete frozen test definitions exactly match the current catalog. Evidence for every reused test is physically copied into the new run, and `resume.json` records every reuse/rerun decision. `FAIL`, `BLOCKED`, `SKIPPED`, missing/new tests, and tests with changed procedures, rationale, mappings, or acceptance policy execute again. This prevents an old pass from concealing a changed qualification procedure.

The setup sections intentionally prevent USB power from invalidating restart tests:

| Section | Required physical state | Important restriction |
|---|---|---|
| `software` | No ESP32 required | Docker is still required for MySQL integration checks. |
| `ble_no_uart` | Box on battery/intended supply, sensors connected, built-in PC Bluetooth on | Disconnect the ESP32 PC micro-USB/UART cable. |
| `power_cycle_no_uart` | Box powered only through its switched battery/intended supply | Remove every USB/UART power path. Closing ESP-IDF Monitor alone does not let the ESP32 turn off. |
| `uart_live` | ESP32 micro-USB connected to the PC, box remains on, BLE/UI connected | Close ESP-IDF Monitor and do not restart or power-cycle the box. The runner owns the UART port. |

If `THERMOMETER_UART_PORT` is not already set when the UART section begins, the runner lists detected serial ports and asks which one belongs to the ESP32. Every confirmation is saved to `setup-transitions.json` and displayed on the dashboard.

This distinction is deliberate: a passing unit, simulator, API, or browser test cannot by itself pass a physical requirement. The test catalog’s `limitations` and `human_intervention` fields, the Markdown summary, CSV coverage report, and dashboard all identify the remaining operator evidence.

Guided procedures read their typed measurement fields from `manual/fields.json`. Numeric limits (including the 10-second history/startup limits and sub-1-second display response), minimum trial/record counts, and required yes/no observations are validated by the runner; an operator cannot record `PASS` when a captured value violates those criteria. Shared instrumentation helpers in `core/instrumentation.py` provide monotonic timing, redacted timestamped logs, HTTP capture, and standard SQL/CSV/EXPLAIN evidence.

## Outcomes and artifacts

Valid test outcomes are `PASS`, `PASS_OVERRIDE` (displayed as **PASS (OVERRIDE)**), `FAIL`, `BLOCKED`, `SKIPPED`, and `NOT_APPLICABLE`. Every post-run edit requires an operator and an evidence-based comment. Use `PASS_OVERRIDE` only when retained evidence proves the test actually passed despite the original result; the original outcome/reason and the complete adjudication history remain in `results.jsonl`. Jira requirements marked `TBD` or `Conflict` remain `BLOCKED` even when related implementation tests pass.

A complete run exits `0`; failed assertions exit `1`; an otherwise successful but incomplete/blocked run exits `2`. This keeps a pending stakeholder decision or missing human evidence distinct from a product failure.

Each run writes to `artifacts/verification/<run-id>/`:

- `run.json` with Git/tool/environment/catalog hashes;
- `results.jsonl` and `junit.xml`;
- `requirements-coverage.json` and `.csv`;
- `fixture-status.json` and `instrumentation-status.json`;
- `summary.md`;
- `resume.json` for resumed runs, including the source and every per-test reuse/rerun decision;
- redacted evidence under `evidence/<TEST-ID>/`.

The dashboard is loopback-only at `http://127.0.0.1:8765`. Its server exposes only dashboard assets and generated verification artifacts, not repository configuration or `.env` files. Manual and semi-automated rows are highlighted, reused rows identify their source run, and every row opens a full result editor. The editor shows the frozen description, rationale, required hardware setup, manual steps or automated command/workflow, pass policy, limitations, measurements, and retained evidence before accepting a decision. It supports every outcome plus **PASS (OVERRIDE)** and requires an operator name and evidence-based comment. Each update is written directly to that run's `results.jsonl`, preserves the original outcome and adjudication history, recalculates coverage/JUnit/summary/dashboard artifacts, and is automatically incorporated the next time `generate_report.py` creates Markdown, LaTeX, or PDF output.

For SYS-04, you may set `THERMOMETER_UART_PORT` in advance (for example `COM8`) and optionally `THERMOMETER_UART_BAUD` (default `115200`), or select the detected port when the UART section begins. Close ESP-IDF Monitor during capture because only one process can normally own the serial port. The runner uses Playwright on the live GUI and firmware `VERIFY DISPLAY_RENDER` UART markers; missing UART produces BLOCKED instead of an operator-reaction-time measurement. SYS-03 and every other power/restart test explicitly run earlier with the UART cable physically disconnected.

FW-04 uses the same UART session to detect each debounced physical button press and its matching `VERIFY LOCAL_DISPLAY_RENDER` marker automatically. Press the requested button within 30 seconds; no typed press confirmation is required. `THERMOMETER_BUTTON_TIMEOUT_SECONDS` can increase that window when necessary.

For SYS-05 on Windows, run `frontend\configure-smtp.ps1` before starting the frontend. The script securely prompts for a Gmail address and Google App Password, writes live SMTP settings only to the gitignored `backend/.env`, and never prints the password. Restart `frontend/run.ps1` afterward so the container receives `EMAIL_MODE=live`. Linux users set the equivalent `EMAIL_MODE=live`, `SMTP_USER`, `SMTP_PASS`, and optional SMTP host/port/from values directly in `backend/.env` before restarting `frontend/run.sh`.

`generate_report.py` creates `document/qualification-report.md` and `.tex` inside the selected run, plots each assisted `sample-timeline.csv`, embeds screenshots/graphs, and includes a Jira-linked requirement matrix plus a section for every test. `--include-requirement-pages` adds the future-facing one-page-per-requirement rationale appendix.

## Safety and known gaps

- Database qualification creates and destroys only a uniquely named disposable MySQL 8.4 container. It never targets the development database.
- Evidence redaction removes common authorization, cookie, PIN/passkey, token, password, and MySQL URL secrets.
- `BE-04` and `DB-03` verify the approved direct-backend command path and deliberate absence of a MySQL command queue.
- `FE-05` verifies the approved trusted-local/no-account model, loopback/CORS boundary, and input validation.
- `FE-06` verifies MySQL-backed email-only configuration and Gmail-compatible SMTP behavior; SYS-05 still requires controlled inbox confirmation.
- Physical construction, accuracy, LCD/button behavior, BLE radio behavior, complete data flow, latency, and controlled end-to-end notifications require the procedures in `manual/`.

## Jira snapshot maintenance

The runner does not mutate Jira. Refreshing or comparing the snapshot is an explicit read-only repository-maintenance task using the Atlassian connector. Any snapshot change must be reviewed together with `tests.yaml`; `DOC-01` fails if an active requirement becomes unmapped.
