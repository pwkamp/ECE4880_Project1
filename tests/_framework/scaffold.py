"""Generate the 56 reviewed test folders from the frozen CSV matrix."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from tests._framework.discovery import tests_root
from tests._framework.io import load_data


GENERATED_MARKER = "<!-- Generated from tests/test_matrix.lock.csv; edit the frozen source through review. -->"

FOLDER_NAMES = {
    "GOV-001": "gov_001_requirements_baseline",
    "DOC-001": "doc_001_design_dossier",
    "SYS-001": "sys_001_integrated_prototype",
    "SYS-002": "sys_002_power_on_recovery",
    "SYS-003": "sys_003_remote_display_under_1s",
    "SYS-004": "sys_004_email_sms_delivery",
    "HW-001": "hw_001_cables_connectors_labels",
    "HW-002": "hw_002_immersion_range_accuracy",
    "HW-003": "hw_003_enclosure_drop",
    "HW-004": "hw_004_hot_plug_recovery",
    "HW-005": "hw_005_battery_power_switch",
    "HW-006": "hw_006_esp32_idf_ble_compatibility",
    "HW-007": "hw_007_lcd_backlight_acceptance",
    "HW-008": "hw_008_usb_c_misconnection_safety",
    "HW-009": "hw_009_thermal_response",
    "FW-001": "fw_001_build_startup",
    "FW-002": "fw_002_dual_sensor_acquisition",
    "FW-003": "fw_003_circular_history",
    "FW-004": "fw_004_sensor_state_recovery",
    "FW-005": "fw_005_local_display_content",
    "FW-006": "fw_006_button_render_20ms",
    "FW-007": "fw_007_backlight_control",
    "FW-008": "fw_008_snapshot_boot_identity",
    "FW-009": "fw_009_shared_display_state",
    "BLE-001": "ble_001_gatt_requester_only",
    "BLE-002": "ble_002_current_display_roundtrip",
    "BLE-003": "ble_003_history_mtu",
    "BLE-004": "ble_004_security_authentication",
    "BLE-005": "ble_005_protocol_conformance",
    "BLE-006": "ble_006_link_loss_recovery",
    "CON-001": "con_001_service_lifecycle",
    "CON-002": "con_002_poll_publish_1hz",
    "CON-003": "con_003_failure_isolation",
    "CON-004": "con_004_history_reconciliation",
    "CON-005": "con_005_control_lifecycle",
    "CON-006": "con_006_reconnect_state_publication",
    "CON-007": "con_007_startup_history_10s",
    "CON-008": "con_008_power_recovery_10s",
    "DB-001": "db_001_schema_types_utc",
    "DB-002": "db_002_uniqueness_query_retention",
    "DB-003": "db_003_users_roles_alert_schema",
    "DB-004": "db_004_control_queue",
    "DB-005": "db_005_secret_externalization",
    "WEB-001": "web_001_current_history_refresh",
    "WEB-002": "web_002_responsive_roles",
    "WEB-003": "web_003_alert_settings_crud",
    "WEB-004": "web_004_graph_series_average",
    "WEB-005": "web_005_units_no_storage_mutation",
    "WEB-006": "web_006_missing_fault_offscale",
    "WEB-007": "web_007_confirmed_remote_display",
    "WEB-008": "web_008_fixed_graph_window",
    "WEB-009": "web_009_extension_approval_gate",
    "WEB-010": "web_010_auth_rbac_sessions",
    "ALR-001": "alr_001_rule_evaluation",
    "ALR-002": "alr_002_episode_deduplication",
    "ALR-003": "alr_003_provider_delivery_isolation",
}

FIRST_IMPLEMENTED = {"FW-001", "HW-006", "BLE-005", "CON-001", "DB-005"}

SPECIALIZED_PROFILES = {
    "GOV": ("manual", "manual", ["human-review"]),
    "DOC": ("manual", "manual", ["human-review"]),
    "SYS-001": ("full-hardware", "semi-automated", ["full-system-bench", "mysql", "web-console"]),
    "SYS-002": ("hil-physical", "semi-automated", ["esp32", "power-relay", "mysql", "web-console"]),
    "SYS-003": ("hil-physical", "semi-automated", ["esp32", "ble", "lcd", "browser"]),
    "SYS-004": ("external", "semi-automated", ["mysql", "web-console", "email-sandbox", "sms-sandbox"]),
    "HW-001": ("full-hardware", "manual", ["final-hardware", "measurement-tools", "human-review"]),
    "HW-002": ("full-hardware", "semi-automated", ["final-hardware", "reference-thermometer"]),
    "HW-003": ("full-hardware", "manual", ["final-hardware", "drop-fixture", "human-review"]),
    "HW-004": ("hil-physical", "semi-automated", ["real-sensors", "sensor-switching", "esp32"]),
    "HW-005": ("hil-physical", "semi-automated", ["final-power-design", "power-analyzer", "power-relay"]),
    "HW-006": ("unit", "automated", ["esp-idf", "device-config"]),
    "HW-007": ("full-hardware", "semi-automated", ["lcd", "backlight-input", "camera", "human-review"]),
    "HW-008": ("hil-physical", "semi-automated", ["hardware-schematics", "usb-c-safety-fixture", "power-analyzer"]),
    "HW-009": ("full-hardware", "semi-automated", ["real-sensors", "reference-thermometer", "thermal-fixture"]),
    "FW": ("hil-sim", "semi-automated", ["esp32", "verification-firmware"]),
    "FW-001": ("unit", "automated", ["esp-idf", "device-config"]),
    "FW-003": ("unit", "automated", ["firmware-unity"]),
    "FW-008": ("unit", "automated", ["firmware-unity"]),
    "FW-009": ("unit", "automated", ["firmware-unity"]),
    "BLE": ("hil-sim", "semi-automated", ["esp32", "ble", "verification-firmware"]),
    "BLE-005": ("unit", "automated", []),
    "CON": ("sitl", "automated", ["scripted-ble"]),
    "CON-005": ("hil-sim", "semi-automated", ["control-path-decision", "verification-firmware", "ble"]),
    "CON-008": ("hil-physical", "semi-automated", ["esp32", "ble", "power-relay", "mysql"]),
    "DB": ("sitl", "automated", ["mysql-test-instance", "production-mysql-adapter"]),
    "DB-005": ("unit", "automated", []),
    "WEB": ("sitl", "automated", ["pr1-console", "browser", "scripted-source"]),
    "ALR": ("sitl", "automated", ["alert-engine", "mysql-test-instance"]),
    "ALR-003": ("external", "semi-automated", ["email-sandbox", "sms-sandbox", "provider-adapters"]),
}


def _specialized(test_id: str) -> tuple[str, str, List[str]]:
    if test_id in SPECIALIZED_PROFILES:
        return SPECIALIZED_PROFILES[test_id]
    return SPECIALIZED_PROFILES[test_id.split("-", 1)[0]]


def _component_owner(test_id: str) -> str:
    return {
        "GOV": "project",
        "DOC": "project",
        "SYS": "system",
        "HW": "hardware",
        "FW": "firmware",
        "BLE": "integration",
        "CON": "connector",
        "DB": "database",
        "WEB": "computer-console",
        "ALR": "alerts",
    }[test_id.split("-", 1)[0]]


def _resources(capabilities: Iterable[str]) -> List[str]:
    values = set(capabilities)
    resources: List[str] = []
    if "ble" in values:
        resources.append("ble-adapter")
    if "esp32" in values:
        resources.append("esp32-under-test")
    if "mysql-test-instance" in values or "mysql" in values:
        resources.append("test-mysql")
    if "email-sandbox" in values or "sms-sandbox" in values:
        resources.append("provider-test-destination")
    if "power-relay" in values:
        resources.append("power-relay")
    return resources


def _split(row: Mapping[str, str], column: str) -> List[str]:
    return [item.strip() for item in row[column].split(";") if item.strip()]


def _load_rows(root: Path) -> List[Dict[str, str]]:
    with (root / "test_matrix.lock.csv").open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _profiles(
    test_id: str,
    legacy_owners: set[str],
    pr1_owners: set[str],
) -> Dict[str, Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Any]] = {}
    if test_id in legacy_owners or test_id in FIRST_IMPLEMENTED:
        capabilities = ["python", "pytest", "jsonschema"]
        if test_id == "CON-001":
            capabilities.append("fastapi")
        if test_id in {"FW-001", "HW-006"}:
            capabilities.extend(["esp-idf", "device-config"])
        credit = "FULL" if test_id in {"HW-006", "CON-001", "DB-005"} else "PARTIAL"
        profiles["unit"] = {
            "automation": "automated",
            "evidence_credit": credit,
            "capabilities": capabilities,
        }
    if test_id in pr1_owners:
        profiles["pr1-unit"] = {
            "automation": "automated",
            "evidence_credit": "PARTIAL",
            "capabilities": [
                "python",
                "pytest",
                "jsonschema",
                "node",
                "npm",
                "pr1-console",
            ],
        }
    if test_id == "BLE-005":
        profiles["cross-language"] = {
            "automation": "automated",
            "evidence_credit": "FULL",
            "capabilities": [
                "python",
                "pytest",
                "jsonschema",
                "c-compiler",
                "node",
                "npm",
                "pr1-console",
            ],
        }
    profile_name, automation, specialized_capabilities = _specialized(test_id)
    if profile_name not in profiles:
        capabilities = [
            "python",
            "pytest",
            "jsonschema",
            *specialized_capabilities,
        ]
        # A harvested unit/Vitest subcase must not make a not-yet-built SITL,
        # HIL, physical, external, or review profile runnable by accident.
        capabilities.append(f"implementation:{test_id}:{profile_name}")
        profiles[profile_name] = {
            "automation": automation,
            "evidence_credit": "FULL" if automation != "manual" else "PARTIAL",
            "capabilities": capabilities,
        }
    return profiles


def render_files(root: Path | None = None) -> Dict[Path, str]:
    root = root or tests_root()
    legacy = load_data(root / "_shared" / "existing_python_tests.json")["owners"]
    pr1 = load_data(root / "_shared" / "pr1_vitest_suites.json")["owners"]
    requirement_lock = load_data(root / "requirements.lock.json")
    locked_by_uid = {item["uid"]: item for item in requirement_lock["requirements"]}
    files: Dict[Path, str] = {}
    for row in _load_rows(root):
        test_id = row["Test ID"].strip()
        folder = root / FOLDER_NAMES[test_id]
        entrypoint = f"test_{test_id.lower().replace('-', '_')}.py"
        uids = _split(row, "Requirements Covered")
        jira_keys = _split(row, "Jira Issues")
        if test_id in FIRST_IMPLEMENTED:
            implementation_status = "implemented"
        elif test_id in legacy or test_id in pr1:
            implementation_status = "harvested"
        else:
            implementation_status = "placeholder"
        profiles = _profiles(test_id, set(legacy), set(pr1))
        specialized_name, _, specialized_caps = _specialized(test_id)
        manifest = {
            "schema_version": 1,
            "id": test_id,
            "name": row["Test Name"],
            "entrypoint": entrypoint,
            "owners": [_component_owner(test_id)],
            "requirements": [
                {"jira": jira, "uid": uid} for uid, jira in zip(uids, jira_keys)
            ],
            "profiles": profiles,
            "timeout_seconds": 900 if test_id in {"FW-001", "HW-006"} else 180,
            "exclusive_resources": _resources(specialized_caps),
            "current_feasibility": row["Current Feasibility"],
            "test_type": row["Primary Test Type"],
            "execution_mode": row["Execution Mode"],
            "implementation": {
                "phase": 2 if implementation_status != "placeholder" else 1,
                "status": implementation_status,
                "python_test_count": len(legacy.get(test_id, [])),
                "pr1_vitest": test_id in pr1,
                "qualification_profile": specialized_name,
            },
        }
        files[folder / "test.yaml"] = json.dumps(manifest, indent=2) + "\n"
        requirements_table = [
            "| UID | Jira | Approved baseline summary |",
            "|---|---|---|",
        ]
        for uid, jira in zip(uids, jira_keys):
            requirements_table.append(
                f"| {uid} | [{jira}](https://pkamp.atlassian.net/browse/{jira}) | {locked_by_uid[uid]['summary']} |"
            )
        profile_lines = [
            f"- {name}: {value['automation']}; {value['evidence_credit']} evidence; "
            f"capabilities: {', '.join(value['capabilities']) or 'none'}."
            for name, value in profiles.items()
        ]
        readme = "\n".join(
            [
                GENERATED_MARKER,
                f"# {test_id}: {row['Test Name']}",
                "",
                f"Primary type: {row['Primary Test Type']}  ",
                f"Execution mode: {row['Execution Mode']}  ",
                f"Current feasibility: {row['Current Feasibility']}  ",
                f"Scaffold status: {implementation_status}",
                "",
                "## Requirements",
                "",
                *requirements_table,
                "",
                "## Purpose and usefulness",
                "",
                row["Why the Procedure Is Useful"],
                "",
                "## Profiles and qualification credit",
                "",
                *profile_lines,
                "",
                "A passing simulated or unit profile does not close a requirement whose full profile requires a physical, external-provider, security, or human boundary.",
                "",
                "## Preconditions and setup",
                "",
                row["Preconditions and Setup"],
                "",
                "## Detailed repeatable procedure",
                "",
                row["Detailed Repeatable Procedure"],
                "",
                "## PASS criteria",
                "",
                row["PASS Criteria"],
                "",
                "## Independent criteria source",
                "",
                row["PASS Criteria Source and Rationale"],
                "",
                "## Test type and automation rationale",
                "",
                row["Why This Test Type and Automation Level"],
                "",
                "## Required instrumentation and observability",
                "",
                row["Required Instrumentation or Project Changes"],
                "",
                "## Evidence retained",
                "",
                row["Evidence to Retain"],
                "",
                "## Safety, cleanup, and known limitations",
                "",
                "The runner performs capability preflight before provisioning and releases every reserved resource during teardown. Missing implementation or equipment is reported as BLOCKED; a required human procedure is MANUAL_REQUIRED. The unresolved architecture and requirement gates documented in tests/README.md must not be converted into passing assumptions.",
                "",
            ]
        )
        files[folder / "README.md"] = readme
        entrypoint_text = (
            '"""Consolidated runner entry point; detailed procedure is in README.md."""\n\n'
            "from tests._framework.entrypoints import run_consolidated\n\n\n"
            f"def test_{test_id.lower().replace('-', '_')}(test_context):\n"
            f"    assert test_context.test_id == {test_id!r}\n"
            "    run_consolidated(test_context)\n"
        )
        files[folder / entrypoint] = entrypoint_text
    return files


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_scaffold(root: Path | None = None) -> None:
    for path, content in render_files(root).items():
        if path.is_file() and path.name == "README.md":
            existing = path.read_text(encoding="utf-8")
            if GENERATED_MARKER not in existing:
                raise RuntimeError(f"refusing to overwrite hand-authored {path}")
        _atomic_write(path, content)


def check_scaffold(root: Path | None = None) -> List[str]:
    differences: List[str] = []
    for path, expected in render_files(root).items():
        if not path.is_file():
            differences.append(f"missing {path}")
        elif path.read_text(encoding="utf-8") != expected:
            differences.append(f"out of date {path}")
    return differences


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        write_scaffold()
        return 0
    differences = check_scaffold()
    for difference in differences:
        print(difference)
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
