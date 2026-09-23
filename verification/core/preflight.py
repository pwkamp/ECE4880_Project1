"""Fixture and instrumentation readiness checks."""

from __future__ import annotations

import shutil
import socket
import urllib.request
from pathlib import Path
from typing import Any

from .tooling import resolve_esp_idf
from .uart_capture import readiness as uart_readiness


READY = "READY"
NOT_READY = "NOT_READY"
CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
WARNING = "WARNING"
NOT_REQUIRED = "NOT_REQUIRED"
CONFIRMED = "CONFIRMED"

# These channels require physical equipment, operator observation, or an
# external capture tool. Calling them READY merely because their name does
# not start with "manual" would overstate what a preflight actually proved.
HUMAN_INSTRUMENTATION = {
    "auth_event_capture",
    "backend_command_timestamp",
    "BLE_transaction_timestamp",
    "ble_transaction_capture",
    "browser_command_timestamp",
    "browser_screenshot",
    "button_event_timestamp",
    "database_command_timeline",
    "ESP32_command_timestamp",
    "esp32_serial_capture",
    "history_transfer_trace",
    "lcd_render_timestamp",
    "manual_disconnect_event_marker",
    "manual_visual_confirmation",
    "mtu_capture",
    "photo_capture",
    "record_reconstruction_check",
    "serial_capture",
}


def _tcp(host: str, port: int) -> tuple[str, str]:
    try:
        with socket.create_connection((host, port), timeout=1):
            return READY, f"{host}:{port} accepting connections"
    except OSError as exc:
        return NOT_READY, str(exc)


def _http(url: str) -> tuple[str, str]:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return (READY, f"HTTP {response.status}") if response.status < 400 else (NOT_READY, f"HTTP {response.status}")
    except Exception as exc:  # readiness diagnostics must not abort preflight
        return NOT_READY, str(exc)


def check_fixture(name: str, fixture: dict[str, Any], repository: Path) -> dict[str, str]:
    check = fixture.get("preflight", {"type": "always"})
    kind = check.get("type", "always")
    if kind == "always":
        status, detail = READY, check.get("detail", "available")
    elif kind == "manual":
        status, detail = CONFIRM_REQUIRED, check.get("prompt", "operator confirmation required")
    elif kind == "esp_idf":
        resolved = resolve_esp_idf(repository)
        if resolved:
            status = READY
            detail = f"{resolved.source}: {' '.join(resolved.command)}"
        else:
            status, detail = NOT_READY, "ESP-IDF idf.py was not found on PATH, in IDF_PATH, VS Code settings, or a standard install"
    elif kind == "tool":
        executable = check["name"]
        found = shutil.which(executable)
        status, detail = (READY, found) if found else (NOT_READY, f"{executable} not found")
    elif kind == "path":
        path = repository / check["path"]
        status, detail = (READY, str(path)) if path.exists() else (NOT_READY, f"missing {path}")
    elif kind == "tcp":
        status, detail = _tcp(check.get("host", "127.0.0.1"), int(check["port"]))
    elif kind == "http":
        status, detail = _http(check["url"])
    else:
        status, detail = WARNING, f"unknown preflight check {kind}"
    return {"name": name, "status": status, "detail": str(detail), "automated": bool(fixture.get("automated"))}


def run_preflight(tests: list[dict[str, Any]], fixtures: dict[str, Any], repository: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    names = sorted({name for test in tests for name in test.get("fixtures", [])})
    fixture_status = {name: check_fixture(name, fixtures[name], repository) for name in names}
    instrumentation_names = sorted({name for test in tests for name in test.get("instrumentation", [])})
    instrumentation_status = {
        name: {
            "name": name,
            "status": CONFIRM_REQUIRED if name.startswith("manual_") or name in HUMAN_INSTRUMENTATION else READY,
            "detail": "operator or external capture confirmation required" if name.startswith("manual_") or name in HUMAN_INSTRUMENTATION else "runner capture available",
        }
        for name in instrumentation_names
    }
    if "esp32_serial_capture" in instrumentation_status:
        ready, detail = uart_readiness()
        instrumentation_status["esp32_serial_capture"] = {
            "name": "esp32_serial_capture",
            "status": READY if ready else CONFIRM_REQUIRED,
            "detail": detail,
        }
    return fixture_status, instrumentation_status


def blockers(test: dict[str, Any], fixture_status: dict[str, Any], instrumentation_status: dict[str, Any]) -> list[str]:
    problems = []
    for name in test.get("fixtures", []):
        if fixture_status[name]["status"] == NOT_READY:
            problems.append(f"fixture {name}: {fixture_status[name]['detail']}")
    for name in test.get("instrumentation", []):
        if instrumentation_status[name]["status"] == NOT_READY:
            problems.append(f"instrumentation {name}: {instrumentation_status[name]['detail']}")
    return problems


def confirmations_pending(test: dict[str, Any], fixture_status: dict[str, Any], instrumentation_status: dict[str, Any]) -> list[str]:
    pending = []
    for name in test.get("fixtures", []):
        if fixture_status[name]["status"] == CONFIRM_REQUIRED:
            pending.append(f"fixture {name}")
    for name in test.get("instrumentation", []):
        if instrumentation_status[name]["status"] == CONFIRM_REQUIRED:
            pending.append(f"instrumentation {name}")
    return pending
