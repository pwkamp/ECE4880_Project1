#!/usr/bin/env python3
"""Entrypoints for the consolidated automated qualification tests.

Exit codes are interpreted by ``verification.runner``: 0 PASS, 1 FAIL,
2 BLOCKED.  Known implementation gaps fail visibly rather than being silently
accepted as a weaker interpretation of Jira.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
FIRMWARE = ROOT / "firmware"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from verification.core.tooling import esp_idf_environment, resolve_esp_idf
BACKEND_PYTHON = (
    BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
)


def run(command: list[str], cwd: Path, *, timeout: int = 600, extra_env: dict[str, str] | None = None) -> int:
    resolved = shutil.which(command[0])
    if resolved:
        command = [resolved, *command[1:]]
    print("$", subprocess.list2cmdline(command))
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join([str(BACKEND), str(ROOT), environment.get("PYTHONPATH", "")])
    if extra_env:
        environment.update(extra_env)
    try:
        process = subprocess.run(command, cwd=cwd, env=environment, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        print(f"ERROR: command timed out after {timeout} seconds", file=sys.stderr)
        return 1
    return process.returncode


def require_files(checks: dict[str, list[str]]) -> int:
    failed = False
    for relative, needles in checks.items():
        path = ROOT / relative
        if not path.exists():
            print(f"FAIL missing {relative}")
            failed = True
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for needle in needles:
            if needle not in content:
                print(f"FAIL {relative} does not contain {needle!r}")
                failed = True
    return 1 if failed else 0


def firmware_build() -> int:
    idf = resolve_esp_idf(ROOT)
    if idf is None:
        print("BLOCKED: ESP-IDF was not found on PATH, through IDF_PATH, VS Code settings, or a standard install")
        return 2
    print(f"Using ESP-IDF from {idf.source}: {idf.idf_path}")
    generated = run([
        sys.executable,
        str(ROOT / "protocol" / "generate_firmware_config.py"),
        "--input", str(ROOT / "protocol" / "thermometer_protocol.json"),
        "--pairing-passkey", "000000",
        "--output", str(FIRMWARE / "build-verification-generated" / "thermometer_protocol_config.h"),
    ], ROOT)
    if generated:
        return generated
    try:
        exported = esp_idf_environment(idf)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"BLOCKED: ESP-IDF environment could not be activated: {exc}")
        return 2
    idf_env = {key: value for key, value in exported.items() if os.environ.get(key) != value}
    configurations = (
        ("real", ROOT / "verification" / "fixtures" / "sdkconfig.real"),
        ("simulated", ROOT / "verification" / "fixtures" / "sdkconfig.simulated"),
    )
    for name, fixture in configurations:
        build_dir = FIRMWARE / f"build-verification-{name}"
        sdkconfig = build_dir / "sdkconfig.qualification"
        if build_dir.exists():
            cleaned = run([*idf.command, "-B", str(build_dir), "fullclean"], FIRMWARE, timeout=300, extra_env=idf_env)
            if cleaned:
                return cleaned
        defaults = f"sdkconfig.defaults;{fixture.as_posix()}"
        built = run(
            [
                *idf.command,
                "--no-ccache",
                "-B", str(build_dir),
                "-D", f"SDKCONFIG={sdkconfig.as_posix()}",
                "-D", f"SDKCONFIG_DEFAULTS={defaults}",
                "build",
            ],
            FIRMWARE,
            timeout=1200,
            extra_env=idf_env,
        )
        if built:
            return built
        generated = (build_dir / "config" / "sdkconfig.h").read_text(encoding="utf-8")
        expected = (
            ["CONFIG_THERMOMETER_SENSOR_BACKEND_REAL 1"]
            if name == "real"
            else ["CONFIG_THERMOMETER_SENSOR_BACKEND_FAKE 1"]
        )
        missing = [value for value in expected if value not in generated]
        if missing:
            print(f"FAIL {name} firmware build used the wrong Kconfig: missing {missing}")
            return 1

    production = (FIRMWARE / "sdkconfig").read_text(encoding="utf-8", errors="replace")
    if "CONFIG_THERMOMETER_SENSOR_BACKEND_REAL=y" not in production:
        print("FAIL production sdkconfig does not select real sensors")
        return 1
    cmake = (FIRMWARE / "main" / "CMakeLists.txt").read_text(encoding="utf-8")
    if '"src/real_display.c"' not in cmake or "hd44780" not in cmake:
        print("FAIL production firmware does not compile the required HD44780 LCD backend")
        return 1
    return 0


def backend_modules(*modules: str) -> int:
    python = str(BACKEND_PYTHON) if BACKEND_PYTHON.exists() else sys.executable
    return run([python, "-m", "unittest", "-v", *modules], ROOT)


def frontend_tests(*files: str) -> int:
    return run(["npm", "test", "--", "--run", *files], FRONTEND)


def doc_integrity() -> int:
    from verification.core.catalog import validate_catalogs
    requirements, tests, _ = validate_catalogs(ROOT / "verification")
    if len(requirements) != 255:
        print(f"FAIL expected 255 Jira requirements, found {len(requirements)}")
        return 1
    if len(tests) != 36:
        print(f"FAIL expected 36 consolidated tests, found {len(tests)}")
        return 1
    unresolved = [item["uid"] for item in requirements if item["status"] in {"tbd", "conflict"}]
    print(f"Catalog valid: 255 requirements, 36 tests, {len(unresolved)} explicitly unresolved")
    return 0


def implementation_gap(name: str, paths_and_needles: dict[str, list[str]]) -> int:
    result = require_files(paths_and_needles)
    if result:
        print(f"FAIL: Jira-required {name} is not fully implemented")
    return result


def firmware_sensor_state_checks() -> int:
    result = require_files({
        "firmware/main/src/thermometer.c": [
            "THERMOMETER_DATA_DISCONNECTED",
            "SWE-EMB-LLR-311",
            "Preserve display_enabled",
        ],
        "firmware/main/src/real_temperature_sensors.c": ["temperature_sensor_read"],
        "firmware/main/src/fake_temperature_sensors.c": ["temperature_sensor_read"],
    })
    source = (FIRMWARE / "main" / "src" / "thermometer.c").read_text(encoding="utf-8")
    start = source.find("static void apply_sensor_reading")
    end = source.find("static void append_history_record", start)
    transition = source[start:end] if start >= 0 and end > start else ""
    if not transition:
        print("FAIL could not isolate apply_sensor_reading")
        return 1
    if "display_enabled =" in transition:
        print("FAIL sensor disconnect/recovery transition overwrites retained display_enabled state")
        return 1
    print("PASS disconnect/recovery transition preserves display_enabled; SYS-02 supplies physical HIL evidence")
    return result


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: qualification_checks.py TEST-ID", file=sys.stderr)
        return 2
    test_id = sys.argv[1]
    if test_id == "FW-01":
        return firmware_build()
    if test_id == "FW-02":
        return firmware_sensor_state_checks()
    if test_id == "FW-03":
        return require_files({
            "firmware/main/src/history_buffer.c": ["HISTORY_CAPACITY", "history_buffer_append"],
            "firmware/main/src/thermometer.c": ["average_valid", "boot_id", "s_latest_sequence"],
        })
    if test_id == "BLE-01":
        return backend_modules("pc_client.tests.test_protocol", "pc_client.tests.test_client")
    if test_id == "BE-01":
        return backend_modules("pc_client.tests.test_ble_service", "pc_client.tests.test_service_components", "pc_client.tests.test_mysql_adapter")
    if test_id == "BE-02":
        return backend_modules("pc_client.tests.test_history_sync", "pc_client.tests.test_mysql_adapter")
    if test_id == "BE-03":
        return backend_modules("pc_client.tests.test_ble_service.BleServiceTests.test_startup_discovers_device_that_is_powered_on_later", "pc_client.tests.test_ble_service.BleServiceTests.test_reconnect_tries_known_target_after_missed_advertisement")
    if test_id == "BE-04":
        result = require_files({
            "backend/pc_client/service_api.py": ["/api/v1/ble/displays/{sensor_id}", "await controller(request).set_display", "DisplayTimeoutError"],
            "backend/pc_client/ble_service.py": ["async def set_display", "RequestPriority.DISPLAY", "_submit_ble"],
            "backend/database/schema.sql": ["CREATE TABLE temperature_samples"],
        })
        schema = (BACKEND / "database" / "schema.sql").read_text(encoding="utf-8")
        if "CREATE TABLE control_commands" in schema:
            print("FAIL database command queue remains in schema")
            return 1
        return result or backend_modules(
            "pc_client.tests.test_service_api.ServiceApiTests.test_all_control_endpoints_return_their_contracts",
            "pc_client.tests.test_ble_service.BleServiceTests.test_display_preempts_history_between_chunks",
            "pc_client.tests.test_ble_service.BleServiceTests.test_late_display_reply_is_confirmed_from_device_state",
        )
    if test_id in {"DB-01", "DB-02", "DB-03"}:
        from verification.checks import mysql_qualification
        try:
            {"DB-01": mysql_qualification.db01, "DB-02": mysql_qualification.db02, "DB-03": mysql_qualification.db03}[test_id]()
        except (OSError, RuntimeError) as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        except AssertionError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    if test_id == "FE-01":
        return frontend_tests("server/app.test.ts", "server/samples.test.ts")
    if test_id == "FE-02":
        result = frontend_tests("src/App.test.tsx", "src/hooks/useThermometer.test.tsx", "src/components/OffScaleBanner.test.tsx")
        if result:
            return result
        return run(["npm", "run", "test:e2e", "--", "readout.spec.ts"], FRONTEND)
    if test_id == "FE-03":
        return frontend_tests("src/lib/chartScroll.test.ts", "src/datasource/pythonBleSource.test.ts", "src/datasource/bleMap.test.ts")
    if test_id == "FE-04":
        config = FRONTEND / "e2e" / "playwright.config.ts"
        if not config.exists() or not (FRONTEND / "node_modules" / "@playwright" / "test").exists():
            print("BLOCKED: Playwright or its viewport suite is not installed")
            return 2
        return run(["npm", "run", "test:e2e", "--", "responsive.spec.ts"], FRONTEND)
    if test_id == "FE-05":
        result = require_files({
            "backend/pc_client/service_api.py": ["Path(ge=1, le=CONFIG.device.sensor_count)", "DisplayRequest", "_configured_cors_origins"],
            "frontend/server/notify.ts": ["AlertEventSchema", "normalizeDestination", "destination is not a valid email"],
        })
        schema = (BACKEND / "database" / "schema.sql").read_text(encoding="utf-8")
        if "CREATE TABLE users" in schema or "password_hash" in schema:
            print("FAIL trusted-local schema contains application user credentials")
            return 1
        return result or backend_modules("pc_client.tests.test_service_api")
    if test_id == "FE-06":
        result = require_files({
            "backend/database/schema.sql": ["CREATE TABLE alert_recipients", "ENUM('EMAIL')", "CREATE TABLE alert_rules"],
            "frontend/src/components/AlertSettings.tsx": ["Alert emails", "valid email", "Recipient enabled", "maximum threshold"],
            "frontend/server/alertConfig.ts": ["PersistedAlertConfigSchema", "createMysqlAlertConfigStore", "recipient.enabled", "recipient.minC"],
            "frontend/src/lib/alertConfigClient.ts": ["/api/alert-config", "saveAlertConfig"],
            "frontend/server/email/smtpSender.ts": ["sendMail"],
            "frontend/server/config.ts": ["smtp.gmail.com", "EMAIL_MODE"],
            "frontend/server/notify.ts": ["normalizeDestination", "composeAlertEmail"],
        })
        if result:
            return result
        result = frontend_tests("server/app.test.ts", "server/alertConfig.test.ts", "server/notify.test.ts", "server/config.test.ts", "src/components/AlertSettings.test.tsx")
        if result:
            return result
        return frontend_tests("src/lib/alertEngine.test.ts")
    if test_id == "FE-07":
        return frontend_tests("src/components/SensorControls.test.tsx", "src/components/DevicePanel.test.tsx", "src/datasource/pythonBleSource.test.ts")
    if test_id == "ALR-01":
        return frontend_tests("src/lib/alertEngine.test.ts")
    if test_id == "ALR-02":
        return frontend_tests("src/lib/alertEngine.test.ts")
    if test_id == "ALR-03":
        return frontend_tests("server/email/index.test.ts", "server/email/consoleSender.test.ts", "server/email/smtpSender.test.ts", "src/hooks/useAlertNotifier.test.tsx")
    if test_id == "DOC-01":
        return doc_integrity()
    print(f"BLOCKED: no automated implementation for {test_id}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
