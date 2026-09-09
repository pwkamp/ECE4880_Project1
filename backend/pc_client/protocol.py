"""Encoding and decoding for the shared ESP32 thermometer protocol."""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any


def _find_shared_protocol_directory() -> Path:
    """Locate the monorepo-owned protocol without depending on the CWD."""

    override = os.environ.get("THERMOMETER_PROTOCOL_DIR")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override).expanduser())

    source = Path(__file__).resolve()
    # Monorepo: repository/backend/pc_client/protocol.py
    candidates.append(source.parents[2] / "protocol")

    for candidate in candidates:
        directory = candidate.resolve()
        if (
            (directory / "thermometer_protocol.json").is_file()
            and (directory / "shared_config.py").is_file()
        ):
            return directory
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise RuntimeError(
        "shared thermometer protocol was not found; keep backend/ and "
        f"protocol/ as siblings or set THERMOMETER_PROTOCOL_DIR (searched: {searched})"
    )


SHARED_PROTOCOL_DIRECTORY = _find_shared_protocol_directory()
# Running `python backend/main.py` puts backend/ rather than the repository
# root on sys.path. Add the shared package's parent before importing its common
# validator; all path lookup remains independent of the process CWD.
shared_parent = str(SHARED_PROTOCOL_DIRECTORY.parent)
if shared_parent not in sys.path:
    sys.path.insert(0, shared_parent)

from protocol.shared_config import load_and_validate


_STRUCT_CODES = {
    "u8": "B",
    "i8": "b",
    "u16": "H",
    "i16": "h",
    "u32": "I",
    "i32": "i",
    "bytes6": "6s",
    "bytes16": "16s",
    "bytes32": "32s",
}


@dataclass(frozen=True)
class BluetoothConfig:
    device_name_prefix: str
    service_uuid: str
    request_characteristic_uuid: str
    response_characteristic_uuid: str
    preferred_att_mtu: int
    advertising_interval_ms: dict[str, int]
    preferred_connection: dict[str, int]


@dataclass(frozen=True)
class DeviceConfig:
    sensor_count: int
    history_capacity_records: int
    sample_period_ms: int
    sampling_task_stack_bytes: int
    sampling_task_priority: int
    failed_reads_before_disconnected: int
    successful_reads_before_reconnected: int
    default_backlight_percent: int


@dataclass(frozen=True)
class ClientConfig:
    connect_timeout_seconds: float
    scan_timeout_seconds: float
    pairing_timeout_seconds: float
    use_cached_gatt_services: bool


@dataclass(frozen=True)
class ServiceConfig:
    api_host: str
    api_port: int
    startup_scan_timeout_seconds: float
    auto_discovery_interval_seconds: float
    recovery_deadline_seconds: float
    poll_interval_seconds: float
    poll_tolerance_seconds: float
    history_sync_budget_seconds: float
    history_chunk_retry_count: int
    display_command_timeout_seconds: float
    completed_operation_retention_seconds: float
    persistence_queue_capacity: int
    credential_registry_filename: str


@dataclass(frozen=True)
class AuthenticationConfig:
    domain_separator: str
    nonce_size_bytes: int
    proof_size_bytes: int
    challenge_timeout_seconds: float
    maximum_failures: int
    lockout_seconds: float


@dataclass(frozen=True)
class ProtocolConfig:
    bluetooth: BluetoothConfig
    device: DeviceConfig
    client: ClientConfig
    service: ServiceConfig
    authentication: AuthenticationConfig
    protocol: dict[str, Any]

    # These compatibility properties keep application code pleasantly short.
    @property
    def protocol_version(self) -> int:
        return int(self.protocol["version"])

    @property
    def device_name_prefix(self) -> str:
        return self.bluetooth.device_name_prefix

    @property
    def service_uuid(self) -> str:
        return self.bluetooth.service_uuid

    @property
    def request_characteristic_uuid(self) -> str:
        return self.bluetooth.request_characteristic_uuid

    @property
    def response_characteristic_uuid(self) -> str:
        return self.bluetooth.response_characteristic_uuid


def _load_config() -> ProtocolConfig:
    config_path = SHARED_PROTOCOL_DIRECTORY / "thermometer_protocol.json"
    raw = load_and_validate(config_path)
    return ProtocolConfig(
        bluetooth=BluetoothConfig(**raw["bluetooth"]),
        device=DeviceConfig(**raw["device"]),
        client=ClientConfig(**raw["client"]),
        service=ServiceConfig(**raw["service"]),
        authentication=AuthenticationConfig(**raw["authentication"]),
        protocol=raw["protocol"],
    )


CONFIG = _load_config()
_LAYOUTS: dict[str, list[dict[str, str]]] = CONFIG.protocol["layouts"]


def _layout_struct(layout_name: str) -> struct.Struct:
    try:
        fields = _LAYOUTS[layout_name]
        format_codes = "".join(_STRUCT_CODES[field["type"]] for field in fields)
    except KeyError as exc:
        raise ValueError(f"invalid protocol layout {layout_name!r}") from exc
    return struct.Struct("<" + format_codes)


def _unpack_layout(layout_name: str, data: bytes) -> dict[str, Any]:
    fields = _LAYOUTS[layout_name]
    packet_struct = LAYOUT_STRUCTS[layout_name]
    if len(data) != packet_struct.size:
        raise ProtocolError(
            f"{layout_name} has {len(data)} bytes; expected {packet_struct.size}"
        )
    return {
        field["name"]: value
        for field, value in zip(fields, packet_struct.unpack(data))
    }


def _pack_layout(layout_name: str, **values: Any) -> bytes:
    fields = _LAYOUTS[layout_name]
    try:
        ordered_values = (values[field["name"]] for field in fields)
        return LAYOUT_STRUCTS[layout_name].pack(*ordered_values)
    except KeyError as exc:
        raise ValueError(f"missing {layout_name} field {exc.args[0]!r}") from exc


LAYOUT_STRUCTS = {name: _layout_struct(name) for name in _LAYOUTS}
HEADER = LAYOUT_STRUCTS["header"]
HEADER_SIZE = HEADER.size
HISTORY_RECORD = LAYOUT_STRUCTS["history_record"]
HISTORY_CHUNK_PREFIX = LAYOUT_STRUCTS["history_chunk_prefix"]

PROTOCOL_VERSION = CONFIG.protocol_version
DEVICE_NAME_PREFIX = CONFIG.device_name_prefix
SERVICE_UUID = CONFIG.service_uuid.lower()
REQUEST_CHARACTERISTIC_UUID = CONFIG.request_characteristic_uuid.lower()
RESPONSE_CHARACTERISTIC_UUID = CONFIG.response_characteristic_uuid.lower()
RESPONSE_FLAG = int(CONFIG.protocol["response_flag"])
MAX_HISTORY_RECORDS_PER_CHUNK = int(
    CONFIG.protocol["max_history_records_per_chunk"]
)

# The JSON is the authority for every wire value used by both implementations.
Opcode = IntEnum(
    "Opcode", {name.upper(): value for name, value in CONFIG.protocol["opcodes"].items()}
)
Status = IntEnum(
    "Status",
    {name.upper(): value for name, value in CONFIG.protocol["status_codes"].items()},
)
VisibleState = IntEnum(
    "VisibleState",
    {name.upper(): value for name, value in CONFIG.protocol["visible_states"].items()},
)
DataStatus = IntEnum(
    "DataStatus",
    {name.upper(): value for name, value in CONFIG.protocol["data_statuses"].items()},
)


class ProtocolError(RuntimeError):
    """Raised for a malformed packet or a non-success response."""

    def __init__(self, message: str, status: Status | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Response:
    version: int
    opcode: Opcode
    request_id: int
    status: Status
    payload: bytes


@dataclass(frozen=True)
class SensorSnapshot:
    sensor_id: int
    temperature_c: float | None
    visible_state: VisibleState
    display_enabled: bool

    @property
    def connected(self) -> bool:
        return self.visible_state is not VisibleState.DISCONNECTED


@dataclass(frozen=True)
class CurrentSnapshot:
    boot_id: int
    newest_sequence: int
    sensors: tuple[SensorSnapshot, ...]
    average_c: float | None


@dataclass(frozen=True)
class DisplayResult:
    sensor_id: int
    visible_state: VisibleState
    display_enabled: bool


@dataclass(frozen=True)
class HistoryMeta:
    boot_id: int
    newest_sequence: int
    counts: tuple[int, ...]
    oldest_sequences: tuple[int, ...]


@dataclass(frozen=True)
class HistoryRecordValue:
    sequence: int
    temperature_c: float | None
    data_status: DataStatus


@dataclass(frozen=True)
class HistoryChunk:
    sensor_id: int
    start_sequence: int
    records: tuple[HistoryRecordValue, ...]


@dataclass(frozen=True)
class AuthenticationChallenge:
    device_id: bytes
    boot_id: int
    nonce: bytes


def validate_passkey(passkey: str) -> str:
    if len(passkey) != 6 or not passkey.isascii() or not passkey.isdigit():
        raise ValueError("passkey must contain exactly six ASCII digits")
    return passkey


def compute_authentication_proof(
    passkey: str, challenge: AuthenticationChallenge
) -> bytes:
    """Prove PIN knowledge without placing the raw PIN in a GATT packet."""

    if len(challenge.device_id) != 6:
        raise ValueError("authentication device identity must contain six bytes")
    if len(challenge.nonce) != CONFIG.authentication.nonce_size_bytes:
        raise ValueError("authentication nonce has an invalid size")
    key = validate_passkey(passkey).encode("ascii")
    message = b"".join(
        (
            CONFIG.authentication.domain_separator.encode("ascii"),
            bytes((PROTOCOL_VERSION,)),
            challenge.device_id,
            challenge.boot_id.to_bytes(4, "little"),
            challenge.nonce,
        )
    )
    return hmac.new(key, message, hashlib.sha256).digest()


def build_request(opcode: Opcode, request_id: int, payload: bytes = b"") -> bytes:
    if not 0 <= request_id <= 0xFFFF:
        raise ValueError("request_id must fit in an unsigned 16-bit integer")
    if len(payload) > 0xFFFF:
        raise ValueError("payload is too long")
    header = _pack_layout(
        "header",
        version=PROTOCOL_VERSION,
        opcode=int(opcode),
        request_id=request_id,
        payload_length=len(payload),
        status=0,
        flags=0,
    )
    return header + payload


def _validate_sensor_id(sensor_id: int) -> None:
    if not 1 <= sensor_id <= CONFIG.device.sensor_count:
        raise ValueError(
            f"sensor_id must be between 1 and {CONFIG.device.sensor_count}"
        )


def build_set_display_request(request_id: int, sensor_id: int, enabled: bool) -> bytes:
    _validate_sensor_id(sensor_id)
    payload = _pack_layout(
        "set_display_request", sensor_id=sensor_id, enabled=int(enabled)
    )
    return build_request(Opcode.SET_DISPLAY, request_id, payload)


def build_authentication_proof_request(request_id: int, proof: bytes) -> bytes:
    if len(proof) != CONFIG.authentication.proof_size_bytes:
        raise ValueError(
            f"authentication proof must contain {CONFIG.authentication.proof_size_bytes} bytes"
        )
    return build_request(
        Opcode.AUTH_PROVE,
        request_id,
        _pack_layout("auth_prove_request", proof=proof),
    )


def build_history_chunk_request(
    request_id: int, sensor_id: int, start_sequence: int, count: int
) -> bytes:
    _validate_sensor_id(sensor_id)
    if not 0 <= start_sequence <= 0xFFFFFFFF:
        raise ValueError("start_sequence must fit in an unsigned 32-bit integer")
    if not 1 <= count <= MAX_HISTORY_RECORDS_PER_CHUNK:
        raise ValueError(f"count must be between 1 and {MAX_HISTORY_RECORDS_PER_CHUNK}")
    payload = _pack_layout(
        "history_chunk_request",
        sensor_id=sensor_id,
        start_sequence=start_sequence,
        record_count=count,
    )
    return build_request(Opcode.GET_HISTORY_CHUNK, request_id, payload)


def parse_response(
    data: bytes | bytearray,
    *,
    expected_opcode: Opcode | None = None,
    expected_request_id: int | None = None,
    allow_error: bool = False,
) -> Response:
    packet = bytes(data)
    if len(packet) < HEADER_SIZE:
        raise ProtocolError(f"response is shorter than the {HEADER_SIZE}-byte header")

    header = _unpack_layout("header", packet[:HEADER_SIZE])
    payload = packet[HEADER_SIZE:]
    if len(payload) != header["payload_length"]:
        raise ProtocolError("response payload length does not match its header")
    if header["flags"] & RESPONSE_FLAG == 0:
        raise ProtocolError("packet is not marked as a response")
    try:
        opcode = Opcode(header["opcode"])
    except ValueError as exc:
        raise ProtocolError(f"unknown response opcode 0x{header['opcode']:02X}") from exc
    try:
        status = Status(header["status"])
    except ValueError as exc:
        raise ProtocolError(f"unknown response status {header['status']}") from exc

    if header["version"] != PROTOCOL_VERSION:
        raise ProtocolError(
            f"protocol version mismatch: client={PROTOCOL_VERSION}, "
            f"server={header['version']}",
            status,
        )
    if expected_opcode is not None and opcode is not expected_opcode:
        raise ProtocolError(
            f"response opcode {opcode.name} does not match {expected_opcode.name}", status
        )
    if expected_request_id is not None and header["request_id"] != expected_request_id:
        raise ProtocolError(
            f"response request ID {header['request_id']} does not match "
            f"{expected_request_id}",
            status,
        )
    if status is not Status.SUCCESS and not allow_error:
        raise ProtocolError(f"ESP32 returned {status.name}", status)

    return Response(header["version"], opcode, header["request_id"], status, payload)


def decode_current(response: Response) -> CurrentSnapshot:
    if response.opcode is not Opcode.GET_CURRENT:
        raise ProtocolError("response is not GET_CURRENT")
    values = _unpack_layout("current_response", response.payload)

    sensors: list[SensorSnapshot] = []
    for sensor_id in range(1, CONFIG.device.sensor_count + 1):
        field_prefix = f"sensor_{sensor_id}_"
        state_raw = values[field_prefix + "visible_state"]
        display_raw = values[field_prefix + "display_enabled"]
        try:
            state = VisibleState(state_raw)
        except ValueError as exc:
            raise ProtocolError(f"invalid visible state {state_raw}") from exc
        if display_raw not in (0, 1):
            raise ProtocolError("display flag is not Boolean")
        temperature = values[field_prefix + "temperature_centi_c"]
        sensors.append(
            SensorSnapshot(
                sensor_id=sensor_id,
                temperature_c=(
                    None if state is VisibleState.DISCONNECTED else temperature / 100
                ),
                visible_state=state,
                display_enabled=bool(display_raw),
            )
        )

    average_valid = values["average_valid"]
    if average_valid not in (0, 1) or values["reserved"] != 0:
        raise ProtocolError("invalid average flags")
    return CurrentSnapshot(
        boot_id=values["boot_id"],
        newest_sequence=values["newest_sequence"],
        sensors=tuple(sensors),
        average_c=(
            values["average_temperature_centi_c"] / 100 if average_valid else None
        ),
    )


def decode_display_result(response: Response) -> DisplayResult:
    if response.opcode is not Opcode.SET_DISPLAY:
        raise ProtocolError("response is not SET_DISPLAY")
    values = _unpack_layout("set_display_response", response.payload)
    _validate_sensor_id(values["sensor_id"])
    if values["enabled"] not in (0, 1):
        raise ProtocolError("display flag is not Boolean")
    try:
        state = VisibleState(values["visible_state"])
    except ValueError as exc:
        raise ProtocolError(f"invalid visible state {values['visible_state']}") from exc
    return DisplayResult(values["sensor_id"], state, bool(values["enabled"]))


def decode_authentication_challenge(response: Response) -> AuthenticationChallenge:
    if response.opcode is not Opcode.AUTH_BEGIN:
        raise ProtocolError("response is not AUTH_BEGIN")
    values = _unpack_layout("auth_begin_response", response.payload)
    return AuthenticationChallenge(
        device_id=values["device_id"],
        boot_id=values["boot_id"],
        nonce=values["nonce"],
    )


def decode_history_meta(response: Response) -> HistoryMeta:
    if response.opcode is not Opcode.GET_HISTORY_META:
        raise ProtocolError("response is not GET_HISTORY_META")
    values = _unpack_layout("history_meta_response", response.payload)
    counts = tuple(
        values[f"sensor_{sensor_id}_count"]
        for sensor_id in range(1, CONFIG.device.sensor_count + 1)
    )
    oldest_sequences = tuple(
        values[f"sensor_{sensor_id}_oldest_sequence"]
        for sensor_id in range(1, CONFIG.device.sensor_count + 1)
    )
    return HistoryMeta(
        values["boot_id"], values["newest_sequence"], counts, oldest_sequences
    )


def decode_history_chunk(response: Response) -> HistoryChunk:
    if response.opcode is not Opcode.GET_HISTORY_CHUNK:
        raise ProtocolError("response is not GET_HISTORY_CHUNK")
    if len(response.payload) < HISTORY_CHUNK_PREFIX.size:
        raise ProtocolError("history chunk is shorter than its prefix")

    prefix = _unpack_layout(
        "history_chunk_prefix", response.payload[: HISTORY_CHUNK_PREFIX.size]
    )
    try:
        _validate_sensor_id(prefix["sensor_id"])
    except ValueError as exc:
        raise ProtocolError(str(exc)) from exc
    if prefix["record_size"] != HISTORY_RECORD.size:
        raise ProtocolError("history record size does not match the shared layout")
    expected_length = (
        HISTORY_CHUNK_PREFIX.size + prefix["record_count"] * HISTORY_RECORD.size
    )
    if len(response.payload) != expected_length:
        raise ProtocolError("history chunk contains an incomplete record")

    records: list[HistoryRecordValue] = []
    for record_index in range(prefix["record_count"]):
        offset = HISTORY_CHUNK_PREFIX.size + record_index * HISTORY_RECORD.size
        values = _unpack_layout(
            "history_record", response.payload[offset : offset + HISTORY_RECORD.size]
        )
        try:
            data_status = DataStatus(values["data_status"])
        except ValueError as exc:
            raise ProtocolError(
                f"invalid history data status {values['data_status']}"
            ) from exc
        records.append(
            HistoryRecordValue(
                sequence=values["sequence"],
                temperature_c=(
                    values["temperature_centi_c"] / 100
                    if data_status is DataStatus.VALID
                    else None
                ),
                data_status=data_status,
            )
        )
    return HistoryChunk(
        prefix["sensor_id"], prefix["start_sequence"], tuple(records)
    )
