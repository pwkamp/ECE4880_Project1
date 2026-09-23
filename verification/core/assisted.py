"""Guided hardware-in-the-loop workflows with machine-collected evidence."""

from __future__ import annotations

import csv
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .evidence import write_json, write_text
from .uart_capture import UartCapture


BACKEND = "http://127.0.0.1:8000"
FRONTEND = "http://127.0.0.1:5173"


def choice(prompt: str, options: list[str]) -> str:
    """Prompt using numbered choices so evidence uses consistent values."""

    print(prompt)
    for number, option in enumerate(options, 1):
        print(f"  {number}. {option}")
    while True:
        raw = input("Select: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        matches = [item for item in options if item.casefold() == raw.casefold()]
        if matches:
            return matches[0]
        print(f"Enter 1-{len(options)}.")


def _json_request(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 5) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _safe(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return {"ok": True, "value": _json_request(method, url, payload)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _snapshot(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "monotonic_ns": time.perf_counter_ns(),
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "ble_status": _safe("GET", f"{BACKEND}/api/v1/ble/status"),
        "current": _safe("GET", f"{BACKEND}/api/v1/ble/current"),
        "samples": _safe("GET", f"{FRONTEND}/api/samples?seconds=600"),
    }


def _duration(seconds: float) -> float:
    """Allow fast framework tests without weakening real-run defaults."""

    scale = float(os.environ.get("VERIFICATION_CAPTURE_SCALE", "1"))
    return max(0.05, seconds * max(0.01, scale))


def capture(label: str, seconds: float, records: list[dict[str, Any]]) -> None:
    actual = _duration(seconds)
    print(f"Capturing {label} for {actual:.0f} seconds...")
    deadline = time.monotonic() + actual
    while True:
        records.append(_snapshot(label))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(1.0, remaining))


def _rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    samples = record.get("samples", {})
    if not samples.get("ok"):
        return []
    value = samples.get("value") or {}
    rows = value.get("rows") or []
    return rows if isinstance(rows, list) else []


def _phase_rows(records: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if record["label"] != label:
            continue
        for row in _rows(record):
            key = str(row.get("observed_at_utc"))
            result[key] = row
    return list(result.values())


def _sensor_valid(row: dict[str, Any], sensor: int) -> bool:
    return row.get(f"sensor{sensor}_status") == "VALID" and row.get(f"sensor{sensor}_c") is not None


def _connected(record: dict[str, Any]) -> bool:
    status = record.get("ble_status", {})
    return bool(status.get("ok") and status.get("value", {}).get("connected") and status.get("value", {}).get("ready"))


def _boot_id(record: dict[str, Any]) -> int | None:
    current = record.get("current", {})
    if not current.get("ok"):
        return None
    value = current.get("value") or {}
    snapshot = value.get("snapshot") or value
    raw = snapshot.get("boot_id") if isinstance(snapshot, dict) else None
    return int(raw) if isinstance(raw, int) else None


def _write_capture(directory: Path, records: list[dict[str, Any]]) -> list[str]:
    jsonl = directory / "assisted-capture.jsonl"
    directory.mkdir(parents=True, exist_ok=True)
    write_text(jsonl, "".join(json.dumps(item, sort_keys=True) + "\n" for item in records))
    csv_path = directory / "sample-timeline.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["phase", "observed_at_utc", "sensor1_c", "sensor1_status", "sensor2_c", "sensor2_status"])
        seen: set[tuple[str, str]] = set()
        for record in records:
            for row in _rows(record):
                key = (record["label"], str(row.get("observed_at_utc")))
                if key in seen:
                    continue
                seen.add(key)
                writer.writerow([record["label"], row.get("observed_at_utc"), row.get("sensor1_c"), row.get("sensor1_status"), row.get("sensor2_c"), row.get("sensor2_status")])
    return [str(jsonl), str(csv_path)]


def _ready_box() -> tuple[bool, str]:
    status = _safe("GET", f"{BACKEND}/api/v1/ble/status")
    if status.get("ok") and status["value"].get("connected") and status["value"].get("ready"):
        return True, "BLE backend reports connected and ready"
    return False, status.get("error") or json.dumps(status.get("value", {}), sort_keys=True)


def _require_box() -> tuple[bool, str]:
    ready, detail = _ready_box()
    if ready:
        return True, detail
    answer = choice("Power the third box, ensure the sensors are connected, and connect it in the web UI.", ["Ready - check now", "Cannot connect - fail this test"])
    if answer.startswith("Cannot"):
        return False, "operator could not connect the third box"
    deadline = time.monotonic() + _duration(30)
    while time.monotonic() < deadline:
        ready, detail = _ready_box()
        if ready:
            return True, detail
        time.sleep(1)
    return False, f"third box did not become connected and ready: {detail}"


def _run_backend_precheck(repository: Path, directory: Path) -> tuple[bool, str]:
    command = [sys.executable, "verification/checks/qualification_checks.py", "BE-01"]
    process = subprocess.run(command, cwd=repository, capture_output=True, text=True, timeout=300, check=False)
    log = directory / "backend-unit-precheck.log"
    write_text(log, f"COMMAND: {command!r}\nEXIT: {process.returncode}\n\n{process.stdout}\n{process.stderr}")
    return process.returncode == 0, str(log)


def _run_qualification_precheck(repository: Path, directory: Path, test_id: str) -> tuple[bool, str]:
    command = [sys.executable, "verification/checks/qualification_checks.py", test_id]
    process = subprocess.run(command, cwd=repository, capture_output=True, text=True, timeout=600, check=False)
    log = directory / f"{test_id.lower()}-precheck.log"
    write_text(log, f"COMMAND: {command!r}\nEXIT: {process.returncode}\n\n{process.stdout}\n{process.stderr}")
    return process.returncode == 0, str(log)


def _sensor_disconnect_workflow(test_id: str, records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    metrics: dict[str, Any] = {}
    capture("baseline", 6, records)
    baseline_boot_ids = {_boot_id(item) for item in records if item["label"] == "baseline"} - {None}
    baseline_boot_id = next(iter(baseline_boot_ids), None)
    metrics["baseline_boot_id"] = baseline_boot_id
    for sensor in (1, 2):
        other = 2 if sensor == 1 else 1
        initial = _display_states().get(sensor)
        desired_states = (True, False) if test_id == "SYS-02" else (initial,)
        for desired in desired_states:
            if desired is None:
                failures.append(f"Sensor {sensor} pre-disconnection display state was unavailable")
                continue
            state_name = "on" if desired else "off"
            response = _safe("PUT", f"{BACKEND}/api/v1/ble/displays/{sensor}", {"enabled": desired})
            state_ready, _, _ = _wait_display(sensor, desired)
            if not response.get("ok") or not state_ready:
                failures.append(f"Sensor {sensor} could not be prepared {state_name.upper()} before disconnect")
                continue
            answer = choice(
                f"Sensor {sensor} is {state_name.upper()}. Disconnect it from the powered third box, then confirm.",
                ["Disconnected", "Cannot perform - block this test"],
            )
            if answer.startswith("Cannot"):
                failures.append(f"BLOCKED: Sensor {sensor} {state_name} disconnect action was not performed")
                continue
            down_label = f"sensor_{sensor}_{state_name}_disconnected"
            capture(down_label, 10, records)
            down = _phase_rows(records, down_label)
            phase_boot_ids = {_boot_id(item) for item in records if item["label"] == down_label} - {None}
            saw_fault = any(not _sensor_valid(row, sensor) for row in down)
            other_continued = sum(_sensor_valid(row, other) for row in down) >= 3
            preserved_while_disconnected = _display_states().get(sensor) == desired
            metrics[f"sensor_{sensor}_{state_name}_fault_observed"] = saw_fault
            metrics[f"sensor_{other}_continued_during_sensor_{sensor}_{state_name}_fault"] = other_continued
            metrics[f"sensor_{sensor}_{state_name}_state_preserved_during_fault"] = preserved_while_disconnected
            metrics[f"sensor_{sensor}_{state_name}_boot_id_unchanged"] = bool(
                baseline_boot_id is not None and phase_boot_ids == {baseline_boot_id}
            )
            if not saw_fault:
                failures.append(f"Sensor {sensor} did not produce a non-valid database state")
            if not other_continued:
                failures.append(f"Sensor {other} did not continue with valid persisted samples")
            if not preserved_while_disconnected:
                failures.append(f"Sensor {sensor} did not preserve {state_name.upper()} while disconnected")
            if baseline_boot_id is None or phase_boot_ids != {baseline_boot_id}:
                failures.append(f"ESP32 boot identity changed or was unavailable during Sensor {sensor} hot-plug")

            answer = choice(f"Reconnect Sensor {sensor}; do not restart the ESP32.", ["Reconnected", "Cannot perform - block this test"])
            if answer.startswith("Cannot"):
                failures.append(f"BLOCKED: Sensor {sensor} {state_name} reconnect action was not performed")
                continue
            up_label = f"sensor_{sensor}_{state_name}_reconnected"
            capture(up_label, 15, records)
            up = _phase_rows(records, up_label)
            recovered = any(_sensor_valid(row, sensor) for row in up[-8:])
            restored = _display_states().get(sensor) == desired
            metrics[f"sensor_{sensor}_{state_name}_automatic_recovery"] = recovered
            metrics[f"sensor_{sensor}_{state_name}_state_restored"] = restored
            if not recovered:
                failures.append(f"Sensor {sensor} did not recover automatically")
            if not restored:
                failures.append(f"Sensor {sensor} did not restore pre-disconnection {state_name.upper()} state")
    return metrics, failures


def _local_state_recovery_workflow(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Verify sensor recovery state locally while the PC BLE link is absent."""

    failures: list[str] = []
    metrics: dict[str, Any] = {}
    for sensor in (1, 2):
        other = 2 if sensor == 1 else 1
        for desired in (True, False):
            state_name = "on" if desired else "off"
            prepared = _safe("PUT", f"{BACKEND}/api/v1/ble/displays/{sensor}", {"enabled": desired})
            state_ready, _, _ = _wait_display(sensor, desired)
            if not prepared.get("ok") or not state_ready:
                failures.append(f"Sensor {sensor} could not be prepared {state_name.upper()}")
                continue
            disconnected = _safe("POST", f"{BACKEND}/api/v1/ble/disconnect")
            if not disconnected.get("ok"):
                failures.append(f"could not disconnect the PC BLE link for Sensor {sensor} {state_name} case")
                continue
            answer = choice(
                f"PC BLE is disconnected. Unplug Sensor {sensor}; verify Sensor {other} continues locally, then reconnect Sensor {sensor} without restarting the ESP32.",
                ["Done; unaffected sensor continued", "Done; unaffected sensor stopped", "Cannot perform - block this test"],
            )
            if answer.startswith("Cannot"):
                failures.append(f"BLOCKED: Sensor {sensor} {state_name} PC-independent recovery action was not performed")
                metrics[f"sensor_{sensor}_{state_name}_local_restore_without_pc"] = None
            elif answer.endswith("stopped"):
                failures.append(f"Sensor {other} did not continue locally while Sensor {sensor} was unplugged")
            if not answer.startswith("Cannot"):
                restored = choice(
                    f"After Sensor {sensor} recovered, did its physical LCD return to {state_name.upper()} while the PC remained disconnected?",
                    [f"Yes - restored {state_name.upper()}", "No - wrong state", "Could not inspect - block this test"],
                )
                local_ok = restored.startswith("Yes")
                metrics[f"sensor_{sensor}_{state_name}_local_restore_without_pc"] = local_ok
                if restored.startswith("Could not"):
                    failures.append(f"BLOCKED: Sensor {sensor} {state_name} restored LCD state could not be inspected")
                elif not local_ok:
                    failures.append(f"Sensor {sensor} did not restore {state_name.upper()} without a PC BLE connection")

            reconnect = _safe("POST", f"{BACKEND}/api/v1/ble/reconnect")
            deadline = time.monotonic() + _duration(10)
            connected = False
            while reconnect.get("ok") and time.monotonic() < deadline:
                item = _snapshot(f"sensor_{sensor}_{state_name}_pc_reconnect")
                records.append(item)
                if _connected(item):
                    connected = True
                    break
                time.sleep(0.25)
            confirmed = connected and _display_states().get(sensor) == desired
            metrics[f"sensor_{sensor}_{state_name}_backend_reconfirmed"] = confirmed
            if not connected:
                failures.append(f"backend did not reconnect after Sensor {sensor} {state_name} local test")
            elif not confirmed:
                failures.append(f"backend-reported state did not match restored {state_name.upper()} state for Sensor {sensor}")
    return metrics, failures


def _thermal(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    metrics: dict[str, Any] = {}
    while True:
        raw = input("Reference room thermometer reading [deg C]: ").strip()
        try:
            reference = float(raw)
            break
        except ValueError:
            print("Enter a numeric Celsius value.")
    answer = choice("Leave both sensors stabilized in room air.", ["Stable - start 20 second capture", "Cannot perform - fail"])
    if answer.startswith("Cannot"):
        return metrics, ["BLOCKED: room-temperature stabilization was not performed"]
    capture("room", 20, records)
    room = _phase_rows(records, "room")[-10:]
    for sensor in (1, 2):
        values = [float(row[f"sensor{sensor}_c"]) for row in room if _sensor_valid(row, sensor)]
        median = statistics.median(values) if values else None
        metrics[f"sensor_{sensor}_room_c"] = median
        if median is None or abs(median - reference) > 4:
            failures.append(f"Sensor {sensor} room median is not within 4 C of reference")

    answer = choice("Place both waterproof sensor tips in a stirred ice-water mixture; keep electronics dry.", ["Immersed - start 60 second capture", "Cannot perform - fail"])
    if answer.startswith("Cannot"):
        failures.append("BLOCKED: ice-water immersion was not performed")
        return metrics, failures
    capture("ice_water", 60, records)
    ice = _phase_rows(records, "ice_water")[-12:]
    ice_values: dict[int, float | None] = {}
    for sensor in (1, 2):
        values = [float(row[f"sensor{sensor}_c"]) for row in ice if _sensor_valid(row, sensor)]
        median = statistics.median(values) if values else None
        ice_values[sensor] = median
        metrics[f"sensor_{sensor}_ice_c"] = median
        if median is None or not -2 <= median <= 2:
            failures.append(f"Sensor {sensor} ice-water median is outside -2..2 C")

    answer = choice("Remove and dry both sensors, then hold both sensor tips in your hands.", ["Holding - start 25 second capture", "Cannot perform - fail"])
    if answer.startswith("Cannot"):
        failures.append("BLOCKED: hand-heating action was not performed")
        return metrics, failures
    capture("hand_heat", 25, records)
    hand = _phase_rows(records, "hand_heat")
    for sensor in (1, 2):
        values = [float(row[f"sensor{sensor}_c"]) for row in hand if _sensor_valid(row, sensor)]
        rise = (max(values) - values[0]) if len(values) >= 2 else 0.0
        metrics[f"sensor_{sensor}_hand_rise_c"] = rise
        if rise <= 0.5:
            failures.append(f"Sensor {sensor} hand-heating rise was not observable")

    for sensor in (1, 2):
        answer = choice(f"Safely bring the soldering iron near Sensor {sensor}; avoid damaging the probe or cable.", ["Ready - start 12 second capture", "Cannot perform - fail"])
        if answer.startswith("Cannot"):
            failures.append(f"BLOCKED: Sensor {sensor} soldering-iron action was not performed")
            continue
        label = f"sensor_{sensor}_iron_heat"
        capture(label, 12, records)
        values = [float(row[f"sensor{sensor}_c"]) for row in _phase_rows(records, label) if _sensor_valid(row, sensor)]
        rise = (max(values) - values[0]) if len(values) >= 2 else 0.0
        metrics[f"sensor_{sensor}_iron_rise_c"] = rise
        hand_rise = float(metrics.get(f"sensor_{sensor}_hand_rise_c", 0))
        # A larger rise in less than half the capture time is a conservative
        # machine-checkable interpretation of "more rapidly".
        faster = rise > max(0.5, hand_rise * 0.5)
        metrics[f"sensor_{sensor}_iron_response_faster"] = faster
        if not faster:
            failures.append(f"Sensor {sensor} iron response was not faster than hand response")
    return metrics, failures


def _history(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    metrics: dict[str, Any] = {}
    answer = choice("Allow the powered third box to accumulate 300 seconds of history before continuing.", ["300 seconds accumulated", "Not available - fail"])
    if answer.startswith("Not available"):
        return metrics, ["BLOCKED: 300 seconds of device history were not available"]
    request = _safe("POST", f"{BACKEND}/api/v1/ble/history/sync")
    if not request.get("ok"):
        return metrics, [f"history synchronization request failed: {request.get('error', 'unknown error')}"]
    requested_operation_id = str((request.get("value") or {}).get("operation_id") or "")
    if not requested_operation_id:
        return metrics, ["history synchronization response did not identify the operation"]
    start = time.perf_counter_ns()
    deadline = time.monotonic() + _duration(10)
    max_rows = 0
    sensor_counts = {1: 0, 2: 0}
    sync: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        record = _snapshot("history_sync")
        records.append(record)
        rows = _rows(record)
        max_rows = max(max_rows, len(rows))
        for sensor in (1, 2):
            sensor_counts[sensor] = max(
                sensor_counts[sensor],
                sum(row.get(f"sensor{sensor}_status") not in {None, "MISSING", "NOT_RETRIEVED"} for row in rows),
            )
        if record["ble_status"].get("ok"):
            candidate = record["ble_status"]["value"].get("history_sync")
            if str((candidate or {}).get("operation_id") or "") == requested_operation_id:
                sync = candidate
        # The backend reports RUNNING while synchronization is active and then
        # replaces it with COMPLETE, INCOMPLETE, FAILED, or CANCELLED.  Older
        # verification code checked a field the API has never exposed, which
        # made an otherwise successful run wait until the full deadline.
        sync_state = str((sync or {}).get("state", "")).upper()
        retrieved = list((sync or {}).get("retrieved_counts") or [])
        if sync_state == "COMPLETE" and len(retrieved) >= 2 and min(retrieved[:2]) >= 300:
            break
        time.sleep(0.25)
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    metrics.update(
        history_rows=max_rows,
        sensor_1_history_records=sensor_counts[1],
        sensor_2_history_records=sensor_counts[2],
        history_to_database_ms=round(elapsed_ms, 1),
        history_sync=sync,
        history_operation_id=requested_operation_id,
    )
    if max_rows < 300:
        failures.append(f"only {max_rows}/300 recent database rows became browser-readable")
    for sensor, count in sensor_counts.items():
        if count < 300:
            failures.append(f"only {count}/300 Sensor {sensor} records became browser-readable")
    if not sync or str(sync.get("state", "")).upper() != "COMPLETE":
        failures.append(
            "backend history synchronization did not report COMPLETE "
            f"(last state: {str((sync or {}).get('state', 'unknown'))})"
        )
    expected = list((sync or {}).get("expected_counts") or [])
    retrieved = list((sync or {}).get("retrieved_counts") or [])
    if len(expected) < 2 or min(expected[:2]) < 300:
        failures.append(f"device did not expose 300 records per sensor (expected counts: {expected or 'unknown'})")
    if len(retrieved) < 2 or min(retrieved[:2]) < 300:
        failures.append(f"backend did not retrieve 300 records per sensor (retrieved counts: {retrieved or 'unknown'})")
    if elapsed_ms > 10_000:
        failures.append(f"history recovery took {elapsed_ms:.0f} ms (>10000 ms)")
    visual = choice("Confirm the web graph now displays the recovered pre-connection history.", ["Graph shows recovered history", "Graph does not show it", "Could not inspect"])
    metrics["graph_confirmation"] = visual
    if visual == "Could not inspect":
        failures.append("BLOCKED: browser graph history could not be inspected")
    elif visual != "Graph shows recovered history":
        failures.append("browser graph history was not confirmed")
    return metrics, failures


def _power_cycle_recovery(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    before = _snapshot("before_box_power_off")
    records.append(before)
    boot_id_before = _boot_id(before)
    answer = choice("Switch the third box OFF now.", ["Powered off", "Cannot perform - fail"])
    if answer.startswith("Cannot"):
        return {}, ["BLOCKED: third-box power-off action was not performed"]
    capture("box_powered_off", 8, records)
    saw_loss = any(not _connected(item) for item in records if item["label"] == "box_powered_off")
    answer = choice("Switch the third box ON. Do not click Connect or restart any application.", ["Powered on - start automatic reconnect timer", "Cannot perform - fail"])
    if answer.startswith("Cannot"):
        return {"link_loss_observed": saw_loss}, ["BLOCKED: third-box power-on action was not performed"]
    start = time.perf_counter_ns()
    deadline = time.monotonic() + _duration(10)
    recovered = False
    while time.monotonic() < deadline:
        item = _snapshot("automatic_reconnect")
        records.append(item)
        if _connected(item) and _rows(item):
            recovered = True
            boot_id_after = _boot_id(item)
            break
        time.sleep(0.25)
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    if not saw_loss:
        failures.append("backend did not expose link/power loss")
    if not recovered:
        failures.append("backend/database did not recover automatically within 10 seconds")
    else:
        if boot_id_before is None or boot_id_after is None or boot_id_before == boot_id_after:
            failures.append("ESP32 boot identity did not change across OFF/ON; check for USB/UART back-power")
    return {
        "link_loss_observed": saw_loss,
        "automatic_reconnect": recovered,
        "reconnect_ms": round(elapsed, 1),
        "boot_id_before_power_off": boot_id_before,
        "boot_id_after_power_on": boot_id_after if recovered else None,
        "physical_restart_confirmed": bool(recovered and boot_id_before is not None and boot_id_after is not None and boot_id_before != boot_id_after),
    }, failures


def _ble_gap_history(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Recover history after a real radio gap while the ESP32 stays powered."""

    failures: list[str] = []
    answer = choice(
        "Keep the third box powered and allow it to accumulate at least 300 seconds of history.",
        ["300 seconds accumulated - create BLE-only gap", "Not available - block this test"],
    )
    if answer.startswith("Not available"):
        return {}, ["BLOCKED: 300 seconds of powered device history were not available"]
    before_gap = _safe("GET", f"{BACKEND}/api/v1/ble/status")
    previous_history_operation_id = str(
        (((before_gap.get("value") or {}).get("history_sync") or {}).get("operation_id")) or ""
    )
    radio_off = choice(
        "Keep the ESP32 powered. Disable only the PC Bluetooth radio (Windows Quick Settings or Linux rfkill); do not click Disconnect or turn off the box.",
        ["PC Bluetooth disabled", "Cannot perform - block this test"],
    )
    if radio_off.startswith("Cannot"):
        return {}, ["BLOCKED: host Bluetooth radio could not be disabled while the box remained powered"]
    capture("ble_only_gap_box_powered", 12, records)
    gap_records = [item for item in records if item["label"] == "ble_only_gap_box_powered"]
    link_loss_observed = any(not _connected(item) for item in gap_records)
    if not link_loss_observed:
        failures.append("backend did not expose link loss while the host Bluetooth radio was disabled")

    radio_on = choice(
        "Re-enable the PC Bluetooth radio. Do not click Connect or Reconnect; the backend must recover automatically.",
        ["PC Bluetooth enabled - start timer", "Cannot perform - block this test"],
    )
    if radio_on.startswith("Cannot"):
        return {"link_loss_observed": link_loss_observed}, ["BLOCKED: host Bluetooth radio was not re-enabled for automatic recovery"]
    radio_enabled_ns = time.perf_counter_ns()
    reconnect_deadline = time.monotonic() + _duration(10)
    history_deadline: float | None = None
    connected_ns: int | None = None
    sync: dict[str, Any] | None = None
    recovered = False
    observed_new_sync = False
    while time.monotonic() < reconnect_deadline or (history_deadline is not None and time.monotonic() < history_deadline):
        item = _snapshot("ble_gap_history_recovery")
        records.append(item)
        if _connected(item) and not recovered:
            recovered = True
            connected_ns = time.perf_counter_ns()
            history_deadline = time.monotonic() + _duration(10)
        if item["ble_status"].get("ok"):
            candidate = item["ble_status"]["value"].get("history_sync")
            candidate_id = str((candidate or {}).get("operation_id") or "")
            if (
                (candidate or {}).get("source") == "automatic"
                and candidate_id
                and candidate_id != previous_history_operation_id
            ):
                sync = candidate
                observed_new_sync = True
        retrieved = list((sync or {}).get("retrieved_counts") or [])
        if recovered and str((sync or {}).get("state", "")).upper() == "COMPLETE" and len(retrieved) >= 2 and min(retrieved[:2]) >= 300:
            break
        if not recovered and time.monotonic() >= reconnect_deadline:
            break
        time.sleep(0.25)
    finished_ns = time.perf_counter_ns()
    reconnect_ms = (connected_ns - radio_enabled_ns) / 1_000_000 if connected_ns is not None else None
    history_elapsed_ms = (finished_ns - connected_ns) / 1_000_000 if connected_ns is not None else None
    expected = list((sync or {}).get("expected_counts") or [])
    retrieved = list((sync or {}).get("retrieved_counts") or [])
    complete = str((sync or {}).get("state", "")).upper() == "COMPLETE"
    if not recovered:
        failures.append("backend did not reconnect after the BLE-only gap")
    if not observed_new_sync:
        failures.append("backend did not expose a new automatic history operation after reconnect")
    if not complete:
        failures.append(f"history synchronization did not complete (state: {(sync or {}).get('state', 'unknown')})")
    if len(expected) < 2 or min(expected[:2]) < 300:
        failures.append(f"powered box did not expose 300 records per sensor: {expected or 'unknown'}")
    if len(retrieved) < 2 or min(retrieved[:2]) < 300:
        failures.append(f"backend did not recover 300 records per sensor: {retrieved or 'unknown'}")
    if reconnect_ms is None or reconnect_ms > 10_000:
        failures.append(f"automatic BLE reconnect took {reconnect_ms if reconnect_ms is not None else 'unknown'} ms (>10000 ms)")
    if history_elapsed_ms is None or history_elapsed_ms > 10_000:
        failures.append(f"history recovery after connection took {history_elapsed_ms if history_elapsed_ms is not None else 'unknown'} ms (>10000 ms)")
    visual = choice(
        "Confirm the graph filled the BLE-gap interval from recovered MySQL history.",
        ["Gap was backfilled", "Gap remains", "Could not inspect - block this test"],
    )
    if visual == "Gap remains":
        failures.append("browser graph retained a gap after history recovery")
    elif visual.startswith("Could not"):
        failures.append("BLOCKED: recovered graph history could not be inspected")
    return {
        "ble_only_gap_seconds": 12,
        "box_remained_powered": True,
        "host_bluetooth_radio_toggled": True,
        "link_loss_observed": link_loss_observed,
        "previous_history_operation_id": previous_history_operation_id or None,
        "reconnected": recovered,
        "new_history_operation_observed": observed_new_sync,
        "history_sync": sync,
        "automatic_reconnect_ms": round(reconnect_ms, 1) if reconnect_ms is not None else None,
        "history_recovery_after_connection_ms": round(history_elapsed_ms, 1) if history_elapsed_ms is not None else None,
        "graph_gap_backfill": visual,
    }, failures


def _data_path(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    capture("correlation", 8, records)
    failures: list[str] = []
    latest = records[-1]
    current = latest.get("current", {}).get("value", {}).get("snapshot") or {}
    db_rows = _rows(latest)
    db = db_rows[-1] if db_rows else {}
    matches: dict[str, bool] = {}
    for sensor in (1, 2):
        sensors = {item.get("sensor_id"): item for item in current.get("sensors", [])}
        live = sensors.get(sensor, {}).get("temperature_c")
        stored = db.get(f"sensor{sensor}_c")
        match = live is not None and stored is not None and abs(float(live) - float(stored)) <= 0.25
        matches[f"sensor_{sensor}_backend_database_match"] = match
        if not match:
            failures.append(f"Sensor {sensor} latest backend and MySQL values do not match")
    physical = choice("Compare the current browser readouts/graph and physical LCD with the captured values.", ["Both sensors match at all visible hops", "A value/state does not match", "Could not inspect"])
    if physical == "Could not inspect":
        failures.append("BLOCKED: physical/UI end-to-end correlation could not be inspected")
    elif physical != "Both sensors match at all visible hops":
        failures.append("physical/UI end-to-end correlation was not confirmed")
    return {**matches, "operator_correlation": physical}, failures


def _display_states() -> dict[int, bool]:
    response = _safe("GET", f"{BACKEND}/api/v1/ble/status")
    if not response.get("ok"):
        return {}
    return {int(item["sensor_id"]): bool(item["enabled"]) for item in response["value"].get("displays", [])}


def _wait_display(sensor: int, expected: bool | None, timeout: float = 5) -> tuple[bool, float, bool | None]:
    start = time.perf_counter_ns()
    deadline = time.monotonic() + _duration(timeout)
    observed: bool | None = None
    while time.monotonic() < deadline:
        observed = _display_states().get(sensor)
        if observed is not None and (expected is None or observed == expected):
            return True, (time.perf_counter_ns() - start) / 1_000_000, observed
        time.sleep(0.2)
    return False, (time.perf_counter_ns() - start) / 1_000_000, observed


def _inspection(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    metrics: dict[str, Any] = {}
    for sensor in (1, 2):
        while True:
            try:
                length = float(input(f"Measured Sensor {sensor} cable length [m]: ").strip())
                break
            except ValueError:
                print("Enter a numeric length in metres.")
        metrics[f"sensor_{sensor}_cable_length_m"] = length
        if not 0.9 <= length <= 1.1:
            failures.append(f"Sensor {sensor} cable length {length} m is outside 0.9..1.1 m")
    for key, prompt in (
        ("construction_inspection", "Inspect strain relief, port labels, connector support, power design, and enclosure retention."),
        ("lcd_readability", "Inspect LCD labels, signed values, average, and indoor readability."),
        ("datasheet_range", "Confirm controlled ESP32, sensor, LCD, battery, and regulator datasheets support the required ranges."),
    ):
        answer = choice(prompt, ["Pass", "Fail", "Could not inspect"])
        metrics[key] = answer
        if answer == "Could not inspect":
            failures.append(f"BLOCKED: {key} could not be inspected")
        elif answer != "Pass":
            failures.append(f"{key}: {answer}")
    metrics["component_models_and_revisions"] = input("Component models and datasheet revisions: ").strip()
    capture("powered_inspection_smoke", 5, records)
    if not _connected(records[-1]) or not _rows(records[-1]):
        failures.append("powered connected/data smoke check failed")
    return metrics, failures


def _button_display(records: list[dict[str, Any]], shared_remote: bool) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    metrics: dict[str, Any] = {}
    initial = _display_states()
    for sensor in (1, 2):
        before = initial.get(sensor)
        if before is None:
            failures.append(f"Sensor {sensor} initial display state unavailable")
            continue
        if shared_remote:
            target = not before
            response = _safe("PUT", f"{BACKEND}/api/v1/ble/displays/{sensor}", {"enabled": target})
            remote_ok, remote_ms, observed = _wait_display(sensor, target)
            metrics[f"sensor_{sensor}_remote_command_ms"] = round(remote_ms, 1)
            metrics[f"sensor_{sensor}_remote_confirmed"] = bool(response.get("ok") and remote_ok)
            if not response.get("ok") or not remote_ok:
                failures.append(f"Sensor {sensor} remote display command was not confirmed")
            before = observed if observed is not None else target
        answer = choice(f"Press the physical Sensor {sensor} display button once, then confirm.", ["Pressed", "Cannot perform"])
        if answer.startswith("Cannot"):
            failures.append(f"BLOCKED: Sensor {sensor} physical button action was not performed")
            continue
        changed, elapsed, observed = _wait_display(sensor, not before)
        records.append({"label": "physical_button", "sensor": sensor, "before": before, "after": observed, "backend_observation_ms": elapsed})
        metrics[f"sensor_{sensor}_physical_toggle_observed"] = changed
        if not changed:
            failures.append(f"Sensor {sensor} physical button change was not reflected in backend state")
        initial[sensor] = observed if observed is not None else before
    if shared_remote:
        invalid = _safe("PUT", f"{BACKEND}/api/v1/ble/displays/3", {"enabled": True})
        rejected = not invalid.get("ok") and "422" in invalid.get("error", "")
        metrics["invalid_sensor_rejected"] = rejected
        if not rejected:
            failures.append("invalid sensor identifier was not rejected")
    else:
        lcd = choice("Inspect numeric, OFF, DISCONNECTED, signed, and average LCD rendering.", ["All cases pass", "One or more cases fail", "Could not inspect"])
        backlight = choice("Cycle the selected backlight control through low, medium, and high.", ["Three readable levels pass", "Levels/readability fail", "Not implemented"])
        timing = choice("Does serial/logic-analyzer evidence show the firmware button-to-render software contribution is at most 20 ms?", ["Yes - evidence captured", "No - exceeds 20 ms", "No timing instrument available"])
        metrics.update(lcd_render_confirmation=lcd, backlight_confirmation=backlight, button_render_timing_confirmation=timing)
        if lcd == "Could not inspect": failures.append("BLOCKED: LCD cases could not be inspected")
        elif lcd != "All cases pass": failures.append(f"LCD cases: {lcd}")
        if backlight != "Three readable levels pass": failures.append(f"backlight: {backlight}")
        if timing == "No timing instrument available": failures.append("BLOCKED: no instrument was available for the 20 ms button/render timing")
        elif timing != "Yes - evidence captured": failures.append(f"20 ms timing: {timing}")
    return metrics, failures


def _ble_control(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    states = _display_states()
    target = not states.get(1, False)
    response = _safe("PUT", f"{BACKEND}/api/v1/ble/displays/1", {"enabled": target})
    confirmed, elapsed, _ = _wait_display(1, target)
    malformed_sensor = _safe("PUT", f"{BACKEND}/api/v1/ble/displays/99", {"enabled": True})
    malformed_value = _safe("PUT", f"{BACKEND}/api/v1/ble/displays/1", {"enabled": "invalid"})
    invalid_rejected = all(not item.get("ok") and "422" in item.get("error", "") for item in (malformed_sensor, malformed_value))
    unauthorized = choice("Using the prepared unbonded client, attempt a state-changing write and observe the LCD/state.", ["Write rejected; state unchanged", "Unauthorized change succeeded", "Could not perform"])
    physical = choice("Confirm the authorized command changed the physical LCD.", ["LCD changed correctly", "LCD did not change", "Could not inspect"])
    if not response.get("ok") or not confirmed: failures.append("authorized direct SET_DISPLAY was not confirmed")
    if not invalid_rejected: failures.append("malformed HTTP control inputs were not rejected")
    if unauthorized == "Could not perform": failures.append("BLOCKED: unbonded-client attempt could not be performed")
    elif unauthorized != "Write rejected; state unchanged": failures.append(f"unbonded client result: {unauthorized}")
    if physical == "Could not inspect": failures.append("BLOCKED: physical authorized LCD result could not be inspected")
    elif physical != "LCD changed correctly": failures.append(f"physical authorized result: {physical}")
    records.append({"label": "ble_control", "authorized_response": response, "malformed_sensor": malformed_sensor, "malformed_value": malformed_value})
    return {"authorized_command_ms": round(elapsed, 1), "authorized_confirmed": confirmed, "malformed_inputs_rejected": invalid_rejected, "unauthorized_client": unauthorized, "physical_lcd": physical}, failures


def _display_latency(repository: Path, directory: Path, records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Measure browser-click to firmware-render latency without operator reaction time.

    Playwright clicks the real running UI.  The firmware emits a sparse UART
    marker only after applying and rendering each command.  Correlating those
    two machine timestamps is the end-to-end measurement required by SYS-04.
    """

    display_source = repository / "firmware" / "main" / "src" / "real_display.c"
    display_implementation = display_source.read_text(encoding="utf-8", errors="replace") if display_source.is_file() else ""
    if "not implemented" in display_implementation or "hardware boundary" in display_implementation:
        return {}, ["physical LCD backend is not implemented, so an end-to-end physical render latency cannot be measured"]
    node = shutil.which("node")
    script = repository / "frontend" / "e2e" / "hil-display-latency.mjs"
    if not node or not script.is_file():
        return {}, ["BLOCKED: Node or the live-GUI Playwright latency script is unavailable"]
    try:
        uart = UartCapture.from_environment()
    except Exception as exc:
        return {}, [f"BLOCKED: UART capture is unavailable: {exc}"]

    environment = os.environ.copy()
    environment["VERIFICATION_EVIDENCE_DIR"] = str(directory)
    actions: list[dict[str, Any]] = []
    timings: list[float] = []
    failures: list[str] = []
    command = [node, str(script)]
    try:
        process = subprocess.Popen(
            command,
            cwd=repository / "frontend",
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            try:
                action = json.loads(line)
            except json.JSONDecodeError:
                records.append({"label": "display_latency_playwright_output", "line": line.rstrip()})
                continue
            if action.get("type") != "action":
                continue
            actions.append(action)
            sensor = int(action["sensor"])
            enabled = bool(action["enabled"])
            action_wall_ns = int(action["action_wall_ns"])
            event = uart.wait_for(
                ("VERIFY DISPLAY_RENDER", f"sensor={sensor}", f"enabled={int(enabled)}"),
                after_wall_ns=action_wall_ns,
                timeout=2.0,
            )
            if event is None:
                failures.append(f"trial {action['trial']} produced no matching firmware render marker")
                continue
            elapsed_ms = (event.observed_wall_ns - action_wall_ns) / 1_000_000
            timings.append(elapsed_ms)
            records.append(
                {
                    "label": "display_latency",
                    **action,
                    "uart_line": event.line,
                    "uart_observed_wall_ns": event.observed_wall_ns,
                    "elapsed_ms": round(elapsed_ms, 3),
                }
            )
        stderr = process.stderr.read() if process.stderr else ""
        return_code = process.wait(timeout=45)
        write_text(directory / "live-gui-playwright.log", f"COMMAND: {command!r}\nEXIT: {return_code}\n\n{stderr}")
        if return_code != 0:
            failures.append(f"live-GUI Playwright driver exited {return_code}: {stderr.strip()[-500:]}")
    except subprocess.TimeoutExpired:
        process.kill()
        failures.append("live-GUI Playwright driver exceeded 45 seconds")
    finally:
        uart_events = [
            {
                "observed_wall_ns": event.observed_wall_ns,
                "observed_monotonic_ns": event.observed_monotonic_ns,
                "line": event.line,
            }
            for event in uart.events
        ]
        uart.close()
        write_json(directory / "uart-events.json", uart_events)

    if len(actions) != 20 or len(timings) != 20:
        failures.append(f"only {len(timings)}/20 browser actions had matching firmware render evidence")
    maximum = max(timings, default=None)
    if maximum is not None and maximum >= 1000:
        failures.append(f"maximum measured browser-to-render latency was {maximum:.1f} ms")
    return {
        "browser_actions": len(actions),
        "matched_uart_renders": len(timings),
        "sensor_1_trials": sum(int(item.get("sensor", 0)) == 1 for item in actions),
        "sensor_2_trials": sum(int(item.get("sensor", 0)) == 2 for item in actions),
        "maximum_end_to_end_latency_ms": round(maximum, 1) if maximum is not None else None,
        "all_trials_under_1000_ms": len(timings) == 20 and all(value < 1000 for value in timings),
    }, failures


def _mechanical(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    capture("pre_test_smoke", 6, records)
    pre_valid = bool(_phase_rows(records, "pre_test_smoke")) and _connected(records[-1])
    actions = [
        ("enclosure_drop", "Perform the approved enclosure drop onto the specified safe surface."),
        ("upside_down", "Operate the enclosure upside down and inspect retained components."),
        ("connected_cable_drop", "Perform the approved connected-cable drop; a cable may detach but must not break."),
        ("ordinary_handling", "Perform the ordinary handling/strain-relief inspection."),
        ("sensor_immersion", "Immerse only the approved sensor head/exposed cable region, then dry it."),
    ]
    outcomes: dict[str, str] = {}
    for key, instruction in actions:
        answer = choice(instruction, ["Completed with no disallowed damage", "Completed - damage/failure observed", "Cannot perform"])
        outcomes[key] = answer
        if answer == "Cannot perform":
            failures.append(f"BLOCKED: {key} could not be performed")
        elif answer != "Completed with no disallowed damage":
            failures.append(f"{key}: {answer}")
    capture("post_test_smoke", 10, records)
    post_rows = _phase_rows(records, "post_test_smoke")[-5:]
    post_valid = _connected(records[-1]) and any(_sensor_valid(row, 1) and _sensor_valid(row, 2) for row in post_rows)
    if not pre_valid:
        failures.append("pre-test connected/data smoke check failed")
    if not post_valid:
        failures.append("post-test connected/data smoke check failed")
    return {"pre_test_smoke_pass": pre_valid, "post_test_smoke_pass": post_valid, **outcomes}, failures


def _email(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    health = _safe("GET", f"{FRONTEND}/api/health")
    mode = health.get("value", {}).get("mode") if health.get("ok") else None
    destination = input("Controlled Gmail/email destination (not written to the summary): ").strip()
    failures: list[str] = []
    for transition, celsius in (("HIGH", 63.0), ("LOW", -10.0)):
        payload = {
            "id": f"qualification-{transition.lower()}-{time.time_ns()}",
            "timestamp": int(time.time() * 1000),
            "recipientId": "qualification",
            "ruleId": "qualification",
            "source": "SENSOR_1",
            "transition": transition,
            "destination": destination,
            "message": f"Qualification {transition.lower()} alert",
            "celsius": celsius,
        }
        response = _safe("POST", f"{FRONTEND}/api/notify", payload)
        records.append({"label": "email_delivery", "transition": transition, "response": response})
        if not response.get("ok") or response.get("value", {}).get("status") not in {"sent", "logged"}:
            failures.append(f"{transition} notification endpoint did not accept delivery")
    confirmation = choice("Check the controlled inbox/provider capture for both exact qualification emails.", ["Both HIGH and LOW emails received", "One or both missing", "Provider is console-only / could not inspect"])
    if mode != "live":
        failures.append(f"BLOCKED: frontend email mode is {mode or 'unknown'}, not live SMTP")
    elif confirmation == "Provider is console-only / could not inspect":
        failures.append("BLOCKED: real email inbox could not be inspected")
    elif confirmation != "Both HIGH and LOW emails received":
        failures.append("real email receipt was not confirmed")
    return {"email_mode": mode, "high_low_requests": 2, "inbox_confirmation": confirmation}, failures


def run_assisted(repository: Path, evidence_root: Path, result: dict[str, Any], test: dict[str, Any], defer_photos: bool = False) -> dict[str, Any]:
    """Execute a named guided workflow and return a completed test result."""

    started = time.perf_counter_ns()
    directory = evidence_root / test["id"]
    directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    metrics: dict[str, Any] = {}

    ready, detail = _require_box()
    metrics["initial_hardware_check"] = detail
    if not ready:
        failures.append(detail)
    else:
        workflow = test.get("assisted_workflow", "observe")
        if test["id"] == "BE-01":
            unit_ok, unit_log = _run_backend_precheck(repository, directory)
            metrics["backend_unit_precheck"] = unit_ok
            result["evidence"].append(Path(unit_log).relative_to(evidence_root.parent).as_posix())
            if not unit_ok:
                failures.append("backend worker automated precheck failed")
        for check_id in ({"BLE-03": ("BLE-01", "BE-02"), "SYS-03": ("BE-02",)}.get(test["id"], ())):
            precheck_ok, precheck_log = _run_qualification_precheck(repository, directory, check_id)
            metrics[f"{check_id.lower()}_precheck"] = precheck_ok
            result["evidence"].append(Path(precheck_log).relative_to(evidence_root.parent).as_posix())
            if not precheck_ok:
                failures.append(f"{check_id} history precheck failed")
        if workflow == "sensor_disconnect":
            if test["id"] == "SYS-02":
                observed, issues = _local_state_recovery_workflow(records)
            else:
                observed, issues = _sensor_disconnect_workflow(test["id"], records)
        elif workflow == "power_hotplug":
            observed, issues = _sensor_disconnect_workflow(test["id"], records)
            power_metrics, power_issues = _power_cycle_recovery(records)
            observed.update(power_metrics)
            issues.extend(power_issues)
        elif workflow == "thermal":
            observed, issues = _thermal(records)
        elif workflow == "reconnect":
            observed, issues = _power_cycle_recovery(records)
        elif workflow == "history":
            observed, issues = _history(records)
        elif workflow == "startup_history":
            observed, issues = _power_cycle_recovery(records)
            history_metrics, history_issues = _ble_gap_history(records)
            observed.update(history_metrics)
            issues.extend(history_issues)
        elif workflow == "data_path":
            observed, issues = _data_path(records)
        elif workflow == "display_latency":
            observed, issues = _display_latency(repository, directory, records)
        elif workflow == "mechanical":
            observed, issues = _mechanical(records)
        elif workflow == "inspection":
            observed, issues = _inspection(records)
        elif workflow == "buttons":
            observed, issues = _button_display(records, False)
        elif workflow == "shared_display":
            observed, issues = _button_display(records, True)
        elif workflow == "ble_control":
            observed, issues = _ble_control(records)
        elif workflow == "email":
            observed, issues = _email(records)
        else:
            capture("assisted_observation", 10, records)
            observed, issues = {}, []
            answer = choice(test.get("description", "Confirm the physical acceptance criteria."), ["Pass criteria observed", "Fail criteria observed", "Could not complete"])
            observed["operator_observation"] = answer
            if answer != "Pass criteria observed":
                issues.append(answer)
        metrics.update(observed)
        failures.extend(issues)

    paths = _write_capture(directory, records)
    summary = directory / "assisted-summary.json"
    blocked_reasons = [item.removeprefix("BLOCKED: ") for item in failures if item.startswith("BLOCKED: ")]
    test_failures = [item for item in failures if not item.startswith("BLOCKED: ")]
    write_json(
        summary,
        {
            "metrics": metrics,
            "failures": test_failures,
            "blocked_reasons": blocked_reasons,
            "workflow": test.get("assisted_workflow"),
        },
    )
    result["metrics"] = metrics
    for path in [*paths, str(summary)]:
        result["evidence"].append(Path(path).relative_to(evidence_root.parent).as_posix())
    # Workflows may create screenshots, UART captures, or driver logs directly.
    # Add every such artifact once so the dashboard and qualification document
    # cannot silently omit machine-collected evidence.
    known_evidence = set(result["evidence"])
    for artifact in sorted(path for path in directory.rglob("*") if path.is_file()):
        relative = artifact.relative_to(evidence_root.parent).as_posix()
        if relative not in known_evidence:
            result["evidence"].append(relative)
            known_evidence.add(relative)
    result["duration_ms"] = (time.perf_counter_ns() - started) // 1_000_000
    result["outcome"] = "FAIL" if test_failures else "BLOCKED" if blocked_reasons else "PASS"
    reasons = [*test_failures, *blocked_reasons]
    if reasons:
        result["failure_reason"] = "; ".join(reasons)
    if test.get("requires_photo"):
        if defer_photos:
            result["pending_evidence"] = ["photo_evidence"]
            if result["outcome"] != "FAIL":
                result["outcome"] = "BLOCKED"
            photo_reason = "required photo evidence deferred; attach it with the evidence add command"
            result["failure_reason"] = "; ".join(filter(None, [result.get("failure_reason"), photo_reason]))
        else:
            raw = input("Required photo evidence file path: ").strip()
            source = Path(raw).expanduser()
            if source.is_file():
                photo_dir = directory / "photos"
                photo_dir.mkdir(exist_ok=True)
                destination = photo_dir / source.name
                shutil.copy2(source, destination)
                result["evidence"].append(destination.relative_to(evidence_root.parent).as_posix())
            else:
                if result["outcome"] != "FAIL":
                    result["outcome"] = "BLOCKED"
                photo_reason = "required photo evidence path does not exist"
                result["failure_reason"] = "; ".join(filter(None, [result.get("failure_reason"), photo_reason]))
    return result
