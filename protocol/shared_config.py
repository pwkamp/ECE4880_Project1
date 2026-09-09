"""One validator for the JSON consumed by Python and firmware generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID


TYPE_SIZES = {
    "u8": 1,
    "i8": 1,
    "u16": 2,
    "i16": 2,
    "u32": 4,
    "i32": 4,
    "bytes6": 6,
    "bytes16": 16,
    "bytes32": 32,
}


def layout_details(layout: list[dict[str, str]]) -> tuple[int, dict[str, int]]:
    offset = 0
    offsets: dict[str, int] = {}
    for field in layout:
        name = field.get("name")
        field_type = field.get("type")
        if not isinstance(name, str) or not name:
            raise ValueError("layout fields require a non-empty name")
        if field_type not in TYPE_SIZES:
            raise ValueError(f"unsupported field type: {field_type}")
        if name in offsets:
            raise ValueError(f"duplicate layout field: {name}")
        offsets[name] = offset
        offset += TYPE_SIZES[field_type]
    return offset, offsets


def _positive(section: dict[str, Any], section_name: str, names: tuple[str, ...]) -> None:
    for name in names:
        value = section.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{section_name}.{name} must be positive")


def _validate_uuid(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"bluetooth.{name} must be a UUID string")
    try:
        UUID(value)
    except ValueError as exc:
        raise ValueError(f"bluetooth.{name} is not a valid UUID") from exc


def load_and_validate(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required_sections = {
        "bluetooth",
        "device",
        "simulation",
        "client",
        "service",
        "authentication",
        "protocol",
    }
    missing = required_sections - config.keys()
    if missing:
        raise ValueError(f"shared configuration is missing: {', '.join(sorted(missing))}")

    bluetooth = config["bluetooth"]
    for name in (
        "service_uuid",
        "request_characteristic_uuid",
        "response_characteristic_uuid",
    ):
        _validate_uuid(bluetooth.get(name), name)
    uuid_values = {
        bluetooth[name].lower()
        for name in (
            "service_uuid",
            "request_characteristic_uuid",
            "response_characteristic_uuid",
        )
    }
    if len(uuid_values) != 3:
        raise ValueError("service and characteristic UUIDs must be unique")
    prefix = bluetooth.get("device_name_prefix")
    if not isinstance(prefix, str) or not prefix or len(prefix.encode("utf-8")) > 17:
        raise ValueError("bluetooth.device_name_prefix must be 1 to 17 UTF-8 bytes")
    if not 23 <= bluetooth.get("preferred_att_mtu", 0) <= 517:
        raise ValueError("bluetooth.preferred_att_mtu must be between 23 and 517")
    advertising = bluetooth["advertising_interval_ms"]
    if not 20 <= advertising["minimum"] <= advertising["maximum"] <= 10240:
        raise ValueError("Bluetooth advertising interval range is invalid")
    connection = bluetooth["preferred_connection"]
    if not 7.5 <= connection["minimum_interval_ms"] <= connection["maximum_interval_ms"] <= 4000:
        raise ValueError("Bluetooth connection interval range is invalid")
    if not 0 <= connection["peripheral_latency"] <= 499:
        raise ValueError("Bluetooth peripheral latency must be between 0 and 499")
    minimum_supervision = (
        2
        * (connection["peripheral_latency"] + 1)
        * connection["maximum_interval_ms"]
    )
    if connection["supervision_timeout_ms"] <= minimum_supervision:
        raise ValueError("Bluetooth supervision timeout is too short")

    device = config["device"]
    if device.get("sensor_count") != 2:
        raise ValueError("this protocol revision requires exactly two sensors")
    _positive(
        device,
        "device",
        (
            "history_capacity_records",
            "sample_period_ms",
            "sampling_task_stack_bytes",
            "sampling_task_priority",
            "failed_reads_before_disconnected",
            "successful_reads_before_reconnected",
        ),
    )
    if device["history_capacity_records"] > 0xFFFF:
        raise ValueError("device.history_capacity_records must fit in u16")
    if not 0 <= device["default_backlight_percent"] <= 100:
        raise ValueError("device.default_backlight_percent must be between 0 and 100")

    simulation = config["simulation"]
    if len(simulation.get("sensors", ())) != device["sensor_count"]:
        raise ValueError("simulation.sensors must contain one entry per sensor")

    client = config["client"]
    _positive(
        client,
        "client",
        ("connect_timeout_seconds", "scan_timeout_seconds", "pairing_timeout_seconds"),
    )
    if not isinstance(client.get("use_cached_gatt_services"), bool):
        raise ValueError("client.use_cached_gatt_services must be true or false")

    service = config["service"]
    if service.get("api_host") != "127.0.0.1":
        raise ValueError("service.api_host must remain loopback-only (127.0.0.1)")
    if not 1 <= service.get("api_port", 0) <= 65535:
        raise ValueError("service.api_port must be between 1 and 65535")
    _positive(
        service,
        "service",
        (
            "startup_scan_timeout_seconds",
            "auto_discovery_interval_seconds",
            "recovery_deadline_seconds",
            "poll_interval_seconds",
            "poll_tolerance_seconds",
            "history_sync_budget_seconds",
            "display_command_timeout_seconds",
            "completed_operation_retention_seconds",
            "persistence_queue_capacity",
        ),
    )
    if service["poll_tolerance_seconds"] >= service["poll_interval_seconds"]:
        raise ValueError("service.poll_tolerance_seconds must be shorter than the poll interval")
    if not isinstance(service.get("history_chunk_retry_count"), int) or service["history_chunk_retry_count"] < 0:
        raise ValueError("service.history_chunk_retry_count cannot be negative")
    registry_filename = service.get("credential_registry_filename", "")
    if not registry_filename.endswith(".csv") or Path(registry_filename).name != registry_filename:
        raise ValueError("service.credential_registry_filename must name a CSV file")

    authentication = config["authentication"]
    domain = authentication.get("domain_separator")
    if not isinstance(domain, str) or not domain:
        raise ValueError("authentication.domain_separator cannot be empty")
    try:
        domain.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("authentication.domain_separator must be ASCII") from exc
    if authentication.get("nonce_size_bytes") != 16:
        raise ValueError("authentication.nonce_size_bytes must be 16")
    if authentication.get("proof_size_bytes") != 32:
        raise ValueError("authentication.proof_size_bytes must be 32")
    _positive(
        authentication,
        "authentication",
        ("challenge_timeout_seconds", "maximum_failures", "lockout_seconds"),
    )

    protocol = config["protocol"]
    if not 1 <= protocol.get("version", 0) <= 255:
        raise ValueError("protocol.version must be between 1 and 255")
    if protocol.get("byte_order") != "little":
        raise ValueError("implementations currently support little endian only")
    for collection_name in (
        "opcodes",
        "status_codes",
        "visible_states",
        "data_statuses",
    ):
        values = protocol.get(collection_name, {})
        if not values or len(values.values()) != len(set(values.values())):
            raise ValueError(f"protocol.{collection_name} values must be unique")
        if any(not isinstance(value, int) or not 0 <= value <= 255 for value in values.values()):
            raise ValueError(f"protocol.{collection_name} values must fit in u8")

    layouts = protocol.get("layouts", {})
    required_layouts = {
        "header",
        "current_response",
        "set_display_request",
        "set_display_response",
        "history_meta_response",
        "history_chunk_request",
        "history_chunk_prefix",
        "history_record",
        "auth_begin_response",
        "auth_prove_request",
    }
    if required_layouts - layouts.keys():
        raise ValueError("protocol.layouts is incomplete")
    for layout in layouts.values():
        layout_details(layout)

    maximum_records = protocol.get("max_history_records_per_chunk", 0)
    if not 1 <= maximum_records <= 255:
        raise ValueError("max_history_records_per_chunk must be between 1 and 255")
    header_size, _ = layout_details(layouts["header"])
    prefix_size, _ = layout_details(layouts["history_chunk_prefix"])
    record_size, _ = layout_details(layouts["history_record"])
    maximum_packet_size = header_size + prefix_size + maximum_records * record_size
    if maximum_packet_size > bluetooth["preferred_att_mtu"] - 1:
        raise ValueError("maximum history response does not fit one ATT Read Response")

    return config
