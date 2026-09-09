"""Async client library for the ESP32 thermometer GATT protocol."""

from __future__ import annotations

import asyncio
import sys
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

try:
    from bleak import BleakClient, BleakScanner
except ImportError as exc:
    BleakClient = None  # type: ignore[assignment]
    BleakScanner = None  # type: ignore[assignment]
    BLEAK_IMPORT_ERROR: ImportError | None = exc
else:
    BLEAK_IMPORT_ERROR = None

from .protocol import (
    CONFIG,
    HEADER_SIZE,
    HISTORY_CHUNK_PREFIX,
    HISTORY_RECORD,
    MAX_HISTORY_RECORDS_PER_CHUNK,
    REQUEST_CHARACTERISTIC_UUID,
    RESPONSE_CHARACTERISTIC_UUID,
    SERVICE_UUID,
    AuthenticationChallenge,
    CurrentSnapshot,
    DataStatus,
    DisplayResult,
    HistoryChunk,
    HistoryMeta,
    Opcode,
    ProtocolError,
    Response,
    build_authentication_proof_request,
    build_history_chunk_request,
    build_request,
    build_set_display_request,
    compute_authentication_proof,
    decode_authentication_challenge,
    decode_current,
    decode_display_result,
    decode_history_chunk,
    decode_history_meta,
    parse_response,
    validate_passkey,
)


@dataclass(frozen=True)
class DiscoveredThermometer:
    name: str
    address: str
    device: Any
    rssi: int | None


def display_name(name: str | None, address: str) -> str:
    """Return an advertised name or a stable, human-friendly fallback."""

    if isinstance(name, str):
        cleaned = name.strip()
        if cleaned and cleaned.casefold() not in {"unknown", "(unknown)"}:
            return cleaned
    compact = "".join(character for character in address if character.isalnum())
    suffix = compact[-6:].upper() if len(compact) >= 6 else "UNKNOWN"
    return f"{CONFIG.device_name_prefix}{suffix}"


@dataclass(frozen=True)
class TimedHistoryRecord:
    sensor_id: int
    sequence: int
    sampled_at: datetime
    temperature_c: float | None
    data_status: DataStatus


@dataclass(frozen=True)
class HistorySync:
    meta: HistoryMeta
    anchor: CurrentSnapshot
    records: tuple[TimedHistoryRecord, ...]
    expected_counts: tuple[int, ...] = ()
    retrieved_counts: tuple[int, ...] = ()
    complete: bool = True
    elapsed_seconds: float = 0.0
    failure_reason: str | None = None
    persistence_configured: bool = False
    persisted: bool = False


def describe_ble_error(error: BaseException) -> str:
    """Return useful text even when a WinRT exception has an empty message."""
    message = str(error).strip()
    if message:
        return message

    details: list[str] = []
    seen_values: set[object] = set()
    for attribute in ("winerror", "hresult", "errno"):
        value = getattr(error, attribute, None)
        if value is not None and value not in seen_values:
            details.append(f"{attribute}={value}")
            seen_values.add(value)

    description = type(error).__name__
    if details:
        description += f" ({', '.join(details)})"
    if error.__cause__ is not None:
        description += f": {describe_ble_error(error.__cause__)}"
    return description


class ThermometerBleClient:
    """Serialized requester for all application-level ESP32 traffic."""

    def __init__(
        self,
        target: Any,
        *,
        connect_timeout: float | None = None,
        client_factory: Any | None = None,
        passkey: str | None = None,
        disconnected_callback: Callable[["ThermometerBleClient"], Any] | None = None,
    ) -> None:
        self.target = target
        self.connect_timeout = (
            CONFIG.client.connect_timeout_seconds
            if connect_timeout is None
            else connect_timeout
        )
        self._client_factory = client_factory or BleakClient
        self._passkey = validate_passkey(passkey) if passkey is not None else None
        self._disconnected_callback = disconnected_callback
        self._client: Any | None = None
        self._connect_lock = asyncio.Lock()
        self._pairing_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()
        self._request_id = 0
        self._closed = False

    @staticmethod
    async def discover(timeout: float | None = None) -> list[DiscoveredThermometer]:
        if BLEAK_IMPORT_ERROR is not None or BleakScanner is None:
            raise RuntimeError(
                "Bleak is not installed; from backend run: "
                "python -m pip install -r pc_client/requirements.txt"
            ) from BLEAK_IMPORT_ERROR

        scan_timeout = (
            CONFIG.client.scan_timeout_seconds if timeout is None else timeout
        )
        discovered = await BleakScanner.discover(
            timeout=scan_timeout, return_adv=True
        )
        results: list[DiscoveredThermometer] = []
        values = discovered.values() if isinstance(discovered, dict) else discovered
        for entry in values:
            if isinstance(entry, tuple):
                device, advertisement = entry
                service_uuids = {
                    value.lower() for value in (advertisement.service_uuids or [])
                }
                name = display_name(
                    advertisement.local_name or device.name, device.address
                )
                rssi = getattr(advertisement, "rssi", None)
            else:
                device = entry
                service_uuids = set()
                name = display_name(device.name, device.address)
                rssi = getattr(device, "rssi", None)
            # Requirement: INT-LLR-400 (SCRUM-507). Names are presentation,
            # never compatibility or security identifiers.
            if SERVICE_UUID in service_uuids:
                results.append(
                    DiscoveredThermometer(name, device.address, device, rssi)
                )
        return sorted(results, key=lambda item: item.name.lower())

    @property
    def is_connected(self) -> bool:
        return bool(self._client is not None and self._client.is_connected)

    @property
    def device_name(self) -> str | None:
        """Return the best name exposed by the active transport or scan."""

        if self._client is not None:
            name = getattr(self._client, "name", None)
            if isinstance(name, str) and name.strip():
                return name
        name = getattr(self.target, "name", None)
        return name if isinstance(name, str) and name.strip() else None

    @property
    def mtu_size(self) -> int:
        if self._client is None:
            return 23
        return int(getattr(self._client, "mtu_size", 23))

    def _uses_native_windows_client(self) -> bool:
        return sys.platform == "win32" and self._client_factory is BleakClient

    @property
    def _target_address(self) -> str:
        address = getattr(self.target, "address", self.target)
        if not isinstance(address, str):
            raise TypeError("BLE target must provide a string address")
        return address

    def set_disconnected_callback(
        self, callback: Callable[["ThermometerBleClient"], Any] | None
    ) -> None:
        self._disconnected_callback = callback

    def _handle_bleak_disconnect(self, _client: Any) -> None:
        # Keep the closed backend until the service calls disconnect(). On
        # Windows, Bleak's physical-link callback closes the GATT session but
        # leaves discovered service objects for disconnect() to dispose. If we
        # discard the backend here, those WinRT objects can overlap the next
        # scan/connect attempt after an ESP32 power cycle.
        callback = self._disconnected_callback
        if callback is None:
            return
        result = callback(self)
        if asyncio.iscoroutine(result):
            asyncio.create_task(result)

    def _credential(self, passkey: str | None = None) -> str:
        if passkey is not None:
            self._passkey = validate_passkey(passkey)
        if self._passkey is None:
            raise ValueError("a six-digit passkey is required for this device")
        return self._passkey

    async def pair(self, passkey: str | None = None) -> None:
        """Create or verify the authenticated Windows bond before connecting."""
        credential = self._credential(passkey)
        if not self._uses_native_windows_client():
            return

        from .windows_pairing import pair_device

        async with self._pairing_lock:
            await pair_device(
                self._target_address,
                credential,
                CONFIG.client.pairing_timeout_seconds,
            )

    async def forget_pairing(self) -> None:
        """Disconnect and remove this device's Windows bond on user request."""
        await self.disconnect()
        if not self._uses_native_windows_client():
            raise RuntimeError("resetting BLE pairing is supported only on Windows")

        from .windows_pairing import forget_device

        async with self._pairing_lock:
            await forget_device(self._target_address)

    async def connect(
        self,
        passkey: str | None = None,
        *,
        ensure_pairing: bool = True,
        authenticate: bool = True,
    ) -> None:
        if self._closed:
            raise RuntimeError("client has been closed")
        if self.is_connected:
            return
        if self._client_factory is None:
            raise RuntimeError(
                "Bleak is not installed; from backend run: "
                "python -m pip install -r pc_client/requirements.txt"
            ) from BLEAK_IMPORT_ERROR

        async with self._connect_lock:
            if self.is_connected:
                return
            credential = self._credential(passkey)
            if ensure_pairing:
                await self.pair(credential)

            client_options: dict[str, Any] = {
                "pair": False,
                "timeout": self.connect_timeout,
                "disconnected_callback": self._handle_bleak_disconnect,
            }
            if self._uses_native_windows_client():
                client_options["winrt"] = {
                    "use_cached_services": CONFIG.client.use_cached_gatt_services
                }

            client = self._client_factory(self.target, **client_options)
            try:
                await client.connect()
                # Enumerate every service, then select ours.  On Windows this
                # uses GetGattServicesAsync, the standard Microsoft flow.  A
                # Bleak service filter selects a UUID-specific WinRT overload
                # that some Bluetooth drivers reject with ERROR_BAD_COMMAND.
                services = getattr(client, "services", None)
                if services is not None and hasattr(services, "get_service"):
                    if services.get_service(SERVICE_UUID) is None:
                        raise RuntimeError(
                            "device does not expose thermometer service "
                            f"{SERVICE_UUID}; verify that the latest firmware is running"
                        )
            except Exception as exc:
                try:
                    # Also clean partially-created WinRT services when the
                    # backend no longer reports an active transport.
                    await client.disconnect()
                except Exception:
                    # A cleanup failure must not replace the operation that
                    # actually made connection or discovery fail.
                    pass
                raise RuntimeError(
                    "GATT connection/service discovery failed: "
                    f"{describe_ble_error(exc)}"
                ) from exc

            self._client = client

        if authenticate:
            try:
                await self.authenticate(credential)
            except Exception:
                with suppress(Exception):
                    await self.disconnect()
                raise

    async def disconnect(self) -> None:
        # A write followed by its matching read is one protocol transaction.
        # Teardown waits for that transaction so another GUI operation cannot
        # clear self._client between the two ATT operations.
        async with self._request_lock:
            await self._disconnect_current_client()

    async def _disconnect_current_client(self) -> None:
        """Disconnect while the caller owns, or does not need, _request_lock."""
        async with self._connect_lock:
            client, self._client = self._client, None
            if client is not None:
                await client.disconnect()

    async def close(self) -> None:
        self._closed = True
        await self.disconnect()

    def _next_request_id(self) -> int:
        self._request_id = (self._request_id + 1) & 0xFFFF
        return self._request_id

    async def _exchange_packet(
        self,
        packet: bytes,
        opcode: Opcode,
        request_id: int,
        *,
        allow_error: bool = False,
    ) -> Response:
        if not self.is_connected:
            raise RuntimeError("GATT request requires an established connection")
        async with self._request_lock:
            client = self._client
            if client is None:
                raise RuntimeError("GATT client disappeared during connection setup")
            operation = "request write"
            try:
                await client.write_gatt_char(
                    REQUEST_CHARACTERISTIC_UUID, packet, response=True
                )
                operation = "response read"
                raw = await client.read_gatt_char(RESPONSE_CHARACTERISTIC_UUID)
            except Exception as exc:
                try:
                    await self._disconnect_current_client()
                except Exception:
                    # Preserve the request failure if Windows also reports an
                    # error while releasing the broken GATT session.
                    pass
                raise RuntimeError(
                    f"GATT {operation} failed: {describe_ble_error(exc)}"
                ) from exc

            return parse_response(
                raw,
                expected_opcode=opcode,
                expected_request_id=request_id,
                allow_error=allow_error,
            )

    async def _request(self, opcode: Opcode, payload: bytes = b"") -> Response:
        request_id = self._next_request_id()
        return await self._exchange_packet(
            build_request(opcode, request_id, payload), opcode, request_id
        )

    async def get_current(self) -> CurrentSnapshot:
        return decode_current(await self._request(Opcode.GET_CURRENT))

    async def begin_authentication(self) -> AuthenticationChallenge:
        return decode_authentication_challenge(
            await self._request(Opcode.AUTH_BEGIN)
        )

    async def authenticate(self, passkey: str | None = None) -> None:
        credential = self._credential(passkey)
        challenge = await self.begin_authentication()
        proof = compute_authentication_proof(credential, challenge)
        request_id = self._next_request_id()
        await self._exchange_packet(
            build_authentication_proof_request(request_id, proof),
            Opcode.AUTH_PROVE,
            request_id,
        )

    async def request_bond_reset(self) -> None:
        await self._request(Opcode.RESET_BOND)

    async def set_display(self, sensor_id: int, enabled: bool) -> DisplayResult:
        request_id = self._next_request_id()
        response = await self._exchange_packet(
            build_set_display_request(request_id, sensor_id, enabled),
            Opcode.SET_DISPLAY,
            request_id,
        )
        return decode_display_result(response)

    async def get_history_meta(self) -> HistoryMeta:
        return decode_history_meta(await self._request(Opcode.GET_HISTORY_META))

    async def get_history_chunk(
        self, sensor_id: int, start_sequence: int, count: int
    ) -> HistoryChunk:
        request_id = self._next_request_id()
        response = await self._exchange_packet(
            build_history_chunk_request(
                request_id, sensor_id, start_sequence, count
            ),
            Opcode.GET_HISTORY_CHUNK,
            request_id,
        )
        return decode_history_chunk(response)

    def records_per_chunk(self) -> int:
        # An ATT Read Response spends one byte on its standard opcode.
        att_read_response_header_size = 1
        value_capacity = max(0, self.mtu_size - att_read_response_header_size)
        protocol_overhead = HEADER_SIZE + HISTORY_CHUNK_PREFIX.size
        mtu_count = (value_capacity - protocol_overhead) // HISTORY_RECORD.size
        return max(1, min(MAX_HISTORY_RECORDS_PER_CHUNK, mtu_count))
