"""Shared actions for the first harvested consolidated tests."""

from __future__ import annotations

import json
import re
from typing import List

from tests._framework.test_context import TestContext


PYTHON_HARVEST_OWNERS = {
    "BLE-001", "BLE-002", "BLE-003", "BLE-004", "BLE-005", "BLE-006",
    "CON-001", "CON-002", "CON-003", "CON-004", "CON-005", "CON-006", "CON-008",
    "DB-005", "FW-001", "HW-006", "SYS-003",
}
PR1_UNIT_OWNERS = {
    "BLE-005", "WEB-001", "WEB-005", "WEB-006", "WEB-007", "WEB-008", "WEB-010",
    "ALR-002", "ALR-003", "CON-007", "DB-001", "DB-005",
}


def _check_database_secrets(context: TestContext) -> None:
    forbidden_files: List[str] = []
    secret_hits: List[str] = []
    excluded_parts = {
        ".git",
        ".venv",
        "build",
        "node_modules",
        "results",
        "tests",
        "__pycache__",
    }
    secret_pattern = re.compile(r"(?i)(mysql(?:\+\w+)?://[^:\s/]+:[^@\s]+@|(?:password|secret|token)\s*=\s*['\"][^'\"]+)")
    production_roots = [
        context.repository / "backend",
        context.repository / "firmware",
        context.repository / "protocol",
    ]
    for path in (
        path
        for production_root in production_roots
        for path in production_root.rglob("*")
    ):
        if not path.is_file() or any(part in excluded_parts for part in path.parts):
            continue
        relative = path.relative_to(context.repository).as_posix()
        if path.name.startswith(".env") and path.name != ".env.example":
            forbidden_files.append(relative)
        if path.name in {"paired_devices.csv", "device_config.cmake"}:
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml", ".md", ".sql"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if secret_pattern.search(text) and "<REDACTED>" not in text:
            secret_hits.append(relative)
    context.record_assertion("database_secret_files_externalized", not forbidden_files, ", ".join(forbidden_files) or "no committed environment secret files")
    context.record_assertion("no_literal_database_credentials", not secret_hits, ", ".join(secret_hits) or "no literal database credentials found")


def _check_platform_contract(context: TestContext) -> None:
    cmake = (context.repository / "firmware" / "CMakeLists.txt").read_text(encoding="utf-8")
    defaults = (context.repository / "firmware" / "sdkconfig.defaults").read_text(encoding="utf-8")
    component = (context.repository / "firmware" / "main" / "CMakeLists.txt").read_text(encoding="utf-8")
    context.record_assertion("esp_idf_project_declared", "project(" in cmake and "IDF_PATH" in cmake, "firmware is an ESP-IDF project")
    context.record_assertion("nimble_enabled", "BT_NIMBLE_ENABLED=y" in defaults or "nimble" in component.lower(), "NimBLE is selected by firmware configuration")
    context.record_assertion("esp32_target_documented", (context.repository / "firmware" / "sdkconfig.defaults.esp32").is_file(), "ESP32 target defaults exist")


def _check_protocol_vectors(context: TestContext) -> None:
    from pc_client.protocol import CONFIG, Opcode, Status, build_request

    vectors = json.loads((context.repository / "tests" / "_shared" / "protocol_vectors" / "protocol_vectors.json").read_text(encoding="utf-8"))
    context.record_assertion("protocol_version_vector", CONFIG.protocol_version == vectors["protocol_version"], "Python and golden protocol versions agree")
    for vector in vectors["request_vectors"]:
        encoded = build_request(Opcode[vector["opcode"]], vector["request_id"], bytes.fromhex(vector["payload_hex"]))
        context.record_assertion(f"vector_{vector['name']}", encoded.hex() == vector["packet_hex"], f"observed {encoded.hex()}, expected {vector['packet_hex']}")
    context.record_assertion("status_values", all(int(Status[name]) == value for name, value in vectors["status_values"].items()), "Python status enum matches golden values")


def run_consolidated(context: TestContext) -> None:
    test_id = context.test_id
    ran_action = False
    if test_id in PYTHON_HARVEST_OWNERS:
        context.run_existing_python_tests(test_id)
        ran_action = True
    if test_id == "BLE-005":
        _check_protocol_vectors(context)
        if context.configuration.get("run_c_vectors", False):
            context.run_c_protocol_vectors()
        ran_action = True
    if test_id == "DB-005":
        _check_database_secrets(context)
        ran_action = True
    if test_id in {"FW-001", "HW-006"}:
        _check_platform_contract(context)
        context.firmware.build(float(context.configuration["timeout_seconds"]) * 0.8)
        ran_action = True
    if test_id in PR1_UNIT_OWNERS and context.configuration.get("run_pr1_vitest", False):
        context.run_pr1_vitest(test_id)
        ran_action = True
    if not ran_action:
        raise RuntimeError(f"{test_id} has no implemented action for profile {context.profile}")
