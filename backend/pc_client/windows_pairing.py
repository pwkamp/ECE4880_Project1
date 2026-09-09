"""Small Windows helper for authenticated BLE passkey pairing.

Pairing is deliberately completed before Bleak opens a GATT session.  This
matches Microsoft's BLE pairing examples and keeps Windows-specific behavior
out of the protocol client.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from enum import Enum, auto
from typing import Any

try:
    from winrt.windows.devices.bluetooth import BluetoothLEDevice
    from winrt.windows.devices.enumeration import (
        DeviceInformation,
        DeviceInformationCustomPairing,
        DevicePairingKinds,
        DevicePairingProtectionLevel,
        DevicePairingRequestedEventArgs,
        DevicePairingResultStatus,
        DeviceUnpairingResultStatus,
    )
except ImportError:
    BluetoothLEDevice = None  # type: ignore[assignment]
    DeviceInformation = None  # type: ignore[assignment]
    DeviceInformationCustomPairing = Any  # type: ignore[assignment,misc]
    DevicePairingRequestedEventArgs = Any  # type: ignore[assignment,misc]

    class DevicePairingKinds(Enum):
        PROVIDE_PIN = auto()

    class DevicePairingProtectionLevel(Enum):
        DEFAULT = auto()
        ENCRYPTION_AND_AUTHENTICATION = auto()

    class DevicePairingResultStatus(Enum):
        PAIRED = auto()
        ALREADY_PAIRED = auto()
        FAILED = auto()

    class DeviceUnpairingResultStatus(Enum):
        UNPAIRED = auto()
        ALREADY_UNPAIRED = auto()
        FAILED = auto()


_PAIRING_SUCCEEDED = {
    DevicePairingResultStatus.PAIRED,
    DevicePairingResultStatus.ALREADY_PAIRED,
}
_UNPAIRING_SUCCEEDED = {
    DeviceUnpairingResultStatus.UNPAIRED,
    DeviceUnpairingResultStatus.ALREADY_UNPAIRED,
}


class WindowsPairingError(RuntimeError):
    """Raised when Windows cannot create the required authenticated bond."""


def _status_name(value: Any) -> str:
    return str(getattr(value, "name", value))


def _address_as_integer(address: str) -> int:
    compact = "".join(character for character in address if character.isalnum())
    if len(compact) != 12:
        raise WindowsPairingError(f"invalid Bluetooth address: {address}")
    try:
        return int(compact, 16)
    except ValueError as exc:
        raise WindowsPairingError(f"invalid Bluetooth address: {address}") from exc


async def _open_bluetooth_device(address: str) -> Any:
    """Resolve the scanned address without opening a GATT session."""
    device = await BluetoothLEDevice.from_bluetooth_address_async(
        _address_as_integer(address)
    )
    if device is None:
        raise WindowsPairingError(
            f"Windows could not resolve BLE device {address}; scan again and "
            "make sure the ESP32 is still advertising"
        )
    return device


async def _fresh_device_information(device_id: str) -> Any:
    # Pairing properties on an existing DeviceInformation object can be stale.
    return await DeviceInformation.create_from_id_async(device_id)


def _close_device_handle(bluetooth_device: Any) -> None:
    """Release a temporary WinRT handle without hiding the pairing result.

    Some Windows Bluetooth drivers report ``ERROR_BAD_COMMAND`` from Close
    after a successful pairing.  Closing is only local resource cleanup; the
    authenticated bond has already been verified independently.
    """
    with suppress(OSError):
        bluetooth_device.close()


def _require_authenticated_bond(device_information: Any) -> None:
    pairing = device_information.pairing
    if not pairing.is_paired:
        raise WindowsPairingError("Windows did not retain the BLE pairing")
    if (
        pairing.protection_level
        != DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION
    ):
        raise WindowsPairingError(
            "Windows bond is not authenticated. Select Reset Pairing in the app "
            "and pair again"
        )


async def pair_device(address: str, passkey: str, timeout: float) -> None:
    """Ensure *address* has an authenticated Windows BLE bond.

    The ESP32 is Display Only, so Windows requests Provide Pin and this handler
    supplies the selected device's six-digit passkey automatically.
    """
    if len(passkey) != 6 or not passkey.isascii() or not passkey.isdigit():
        raise ValueError("passkey must contain exactly six ASCII digits")

    bluetooth_device = await _open_bluetooth_device(address)
    try:
        device_id = bluetooth_device.device_information.id
        endpoint = await _fresh_device_information(device_id)
        if endpoint.pairing.is_paired:
            _require_authenticated_bond(endpoint)
            return
        if not endpoint.pairing.can_pair:
            raise WindowsPairingError(
                "Windows reports that this device cannot be paired"
            )

        requested_ceremonies: list[str] = []
        custom_pairing = endpoint.pairing.custom

        def handle_pairing_request(
            _sender: DeviceInformationCustomPairing,
            args: DevicePairingRequestedEventArgs,
        ) -> None:
            requested_ceremonies.append(_status_name(args.pairing_kind))
            if args.pairing_kind == DevicePairingKinds.PROVIDE_PIN:
                args.accept_with_pin(passkey)

        token = custom_pairing.add_pairing_requested(handle_pairing_request)
        try:
            pairing_operation = custom_pairing.pair_with_protection_level_async(
                DevicePairingKinds.PROVIDE_PIN,
                DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION,
            )
            result = await asyncio.wait_for(pairing_operation, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise WindowsPairingError(
                f"Windows pairing timed out after {timeout:g} seconds"
            ) from exc
        except Exception as exc:
            detail = str(exc).strip() or type(exc).__name__
            raise WindowsPairingError(
                f"Windows could not start BLE pairing: {detail}"
            ) from exc
        finally:
            custom_pairing.remove_pairing_requested(token)

        if result.status not in _PAIRING_SUCCEEDED:
            ceremonies = ", ".join(requested_ceremonies) or "none"
            raise WindowsPairingError(
                f"Windows pairing failed: {_status_name(result.status)} "
                f"(ceremonies: {ceremonies}). Select Reset Pairing and try again"
            )

        paired_device = await _fresh_device_information(device_id)
        _require_authenticated_bond(paired_device)
    finally:
        _close_device_handle(bluetooth_device)


async def forget_device(address: str) -> None:
    """Remove the selected device's Windows bond when the user requests it."""
    bluetooth_device = await _open_bluetooth_device(address)
    try:
        endpoint = await _fresh_device_information(
            bluetooth_device.device_information.id
        )
        if not endpoint.pairing.is_paired:
            return

        result = await endpoint.pairing.unpair_async()
        if result.status not in _UNPAIRING_SUCCEEDED:
            raise WindowsPairingError(
                f"Windows could not reset pairing: {_status_name(result.status)}"
            )
    finally:
        _close_device_handle(bluetooth_device)
