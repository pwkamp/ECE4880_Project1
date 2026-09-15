"""Linux BlueZ pairing for the ESP32 passkey bond.

Windows uses WinRT; Linux uses the system D-Bus Agent1 API so the six-digit
firmware PIN can be supplied without bluetoothctl. Scan/connect still go
through Bleak. This module is imported only on Linux production clients.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol


class LinuxPairingError(RuntimeError):
    """Raised when BlueZ cannot create or remove the authenticated bond."""


class BlueZBackend(Protocol):
    async def is_paired(self, address: str) -> bool: ...

    async def pair(self, address: str, passkey: str, timeout: float) -> None: ...

    async def remove(self, address: str) -> None: ...


def normalize_address(address: str) -> str:
    compact = "".join(character for character in address if character.isalnum())
    if len(compact) != 12:
        raise LinuxPairingError(f"invalid Bluetooth address: {address}")
    try:
        int(compact, 16)
    except ValueError as exc:
        raise LinuxPairingError(f"invalid Bluetooth address: {address}") from exc
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper()


def device_object_path(adapter_path: str, address: str) -> str:
    compact = normalize_address(address).replace(":", "_")
    return f"{adapter_path}/dev_{compact}"


def _require_passkey(passkey: str) -> str:
    if len(passkey) != 6 or not passkey.isascii() or not passkey.isdigit():
        raise ValueError("passkey must contain exactly six ASCII digits")
    return passkey


async def pair_device(
    address: str,
    passkey: str,
    timeout: float,
    *,
    backend: BlueZBackend | None = None,
) -> None:
    """Ensure *address* has an authenticated BlueZ LE bond."""

    credential = _require_passkey(passkey)
    normalized = normalize_address(address)
    session = backend or DBusBlueZBackend()
    if await session.is_paired(normalized):
        return
    await session.pair(normalized, credential, timeout)


async def forget_device(
    address: str,
    *,
    backend: BlueZBackend | None = None,
) -> None:
    """Remove the BlueZ device object (and its bond) when the user requests it."""

    normalized = normalize_address(address)
    session = backend or DBusBlueZBackend()
    await session.remove(normalized)


class DBusBlueZBackend:
    """Talk to org.bluez on the system bus via dbus-fast."""

    async def is_paired(self, address: str) -> bool:
        async with _BlueZBus() as bus:
            device = await bus.device_interface(address, discover=False)
            if device is None:
                return False
            return bool(await device.get_paired())

    async def pair(self, address: str, passkey: str, timeout: float) -> None:
        async with _BlueZBus() as bus:
            await bus.pair(address, passkey, timeout)

    async def remove(self, address: str) -> None:
        async with _BlueZBus() as bus:
            await bus.remove(address)


class _BlueZBus:
    def __init__(self) -> None:
        self._bus: Any = None

    async def __aenter__(self) -> "_BlueZBus":
        try:
            from dbus_fast.aio import MessageBus
            from dbus_fast.constants import BusType
        except ImportError as exc:
            raise LinuxPairingError(
                "dbus-fast is required for Linux BLE pairing (installed with bleak)"
            ) from exc
        try:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        except Exception as exc:
            raise LinuxPairingError(
                f"could not connect to the system D-Bus (is this user in group bluetooth?): {exc}"
            ) from exc
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._bus is not None:
            self._bus.disconnect()
            self._bus = None

    async def _managed_objects(self) -> dict[str, Any]:
        assert self._bus is not None
        introspection = await self._bus.introspect("org.bluez", "/")
        obj = self._bus.get_proxy_object("org.bluez", "/", introspection)
        manager = obj.get_interface("org.freedesktop.DBus.ObjectManager")
        return await manager.call_get_managed_objects()

    async def _adapter_path(self) -> str:
        objects = await self._managed_objects()
        for path, interfaces in objects.items():
            if "org.bluez.Adapter1" in interfaces:
                return str(path)
        raise LinuxPairingError("no BlueZ adapter is available")

    async def device_interface(self, address: str, *, discover: bool) -> Any | None:
        assert self._bus is not None
        adapter = await self._adapter_path()
        path = device_object_path(adapter, address)
        objects = await self._managed_objects()
        if path not in objects or "org.bluez.Device1" not in objects[path]:
            if not discover:
                return None
            await self._discover_until_present(adapter, path)
            objects = await self._managed_objects()
        if path not in objects or "org.bluez.Device1" not in objects[path]:
            return None
        introspection = await self._bus.introspect("org.bluez", path)
        obj = self._bus.get_proxy_object("org.bluez", path, introspection)
        return obj.get_interface("org.bluez.Device1")

    async def _discover_until_present(self, adapter_path: str, device_path: str) -> None:
        """One short LE discovery so BlueZ creates the device object. Always stopped."""

        assert self._bus is not None
        from dbus_fast import Variant

        introspection = await self._bus.introspect("org.bluez", adapter_path)
        obj = self._bus.get_proxy_object("org.bluez", adapter_path, introspection)
        adapter = obj.get_interface("org.bluez.Adapter1")
        try:
            await adapter.call_set_discovery_filter(
                {
                    "Transport": Variant("s", "le"),
                    "DuplicateData": Variant("b", False),
                }
            )
        except Exception:
            pass
        try:
            await adapter.call_start_discovery()
            for _ in range(8):
                await asyncio.sleep(0.5)
                objects = await self._managed_objects()
                if (
                    device_path in objects
                    and "org.bluez.Device1" in objects[device_path]
                ):
                    return
        finally:
            try:
                await adapter.call_stop_discovery()
            except Exception:
                pass

    async def pair(self, address: str, passkey: str, timeout: float) -> None:
        from dbus_fast import DBusError

        device = await self.device_interface(address, discover=True)
        if device is None:
            raise LinuxPairingError(
                f"BlueZ does not know device {address}; scan again while the ESP32 is advertising"
            )
        if bool(await device.get_paired()):
            return

        async with _PasskeyAgent(self._bus, passkey) as _agent:
            try:
                await asyncio.wait_for(device.call_pair(), timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise LinuxPairingError(
                    f"BlueZ pairing timed out after {timeout:g} seconds"
                ) from exc
            except DBusError as exc:
                text = str(exc)
                if "AlreadyExists" in text or "Already Exists" in text:
                    return
                raise LinuxPairingError(f"BlueZ pairing failed: {text}") from exc

        if not bool(await device.get_paired()):
            raise LinuxPairingError("BlueZ did not retain the BLE pairing")

    async def remove(self, address: str) -> None:
        from dbus_fast import DBusError

        adapter_path = await self._adapter_path()
        path = device_object_path(adapter_path, address)
        objects = await self._managed_objects()
        if path not in objects:
            return
        device = await self.device_interface(address, discover=False)
        if device is not None:
            try:
                if bool(await device.get_connected()):
                    await device.call_disconnect()
            except Exception:
                pass
        assert self._bus is not None
        introspection = await self._bus.introspect("org.bluez", adapter_path)
        obj = self._bus.get_proxy_object("org.bluez", adapter_path, introspection)
        adapter = obj.get_interface("org.bluez.Adapter1")
        try:
            await adapter.call_remove_device(path)
        except DBusError as exc:
            if "DoesNotExist" in str(exc) or "Does Not Exist" in str(exc):
                return
            raise LinuxPairingError(f"BlueZ could not reset pairing: {exc}") from exc


class _PasskeyAgent:
    """org.bluez.Agent1 that answers Provide PIN with the firmware passkey."""

    def __init__(self, bus: Any, passkey: str) -> None:
        self._bus = bus
        self._passkey = passkey
        self._path = "/ece4880/agent1"
        self._exported = False

    async def __aenter__(self) -> "_PasskeyAgent":
        from dbus_fast.service import ServiceInterface, method

        pin = self._passkey
        pin_int = int(pin)

        class Agent(ServiceInterface):
            def __init__(self) -> None:
                super().__init__("org.bluez.Agent1")

            @method()
            def Release(self) -> None:
                return None

            @method()
            def RequestPinCode(self, _device: "o") -> "s":
                return pin

            @method()
            def DisplayPinCode(self, _device: "o", _pincode: "s") -> None:
                return None

            @method()
            def RequestPasskey(self, _device: "o") -> "u":
                return pin_int

            @method()
            def DisplayPasskey(self, _device: "o", _passkey: "u", _entered: "q") -> None:
                return None

            @method()
            def RequestConfirmation(self, _device: "o", _passkey: "u") -> None:
                return None

            @method()
            def RequestAuthorization(self, _device: "o") -> None:
                return None

            @method()
            def AuthorizeService(self, _device: "o", _uuid: "s") -> None:
                return None

            @method()
            def Cancel(self) -> None:
                return None

        self._bus.export(self._path, Agent())
        self._exported = True
        introspection = await self._bus.introspect("org.bluez", "/org/bluez")
        obj = self._bus.get_proxy_object("org.bluez", "/org/bluez", introspection)
        manager = obj.get_interface("org.bluez.AgentManager1")
        await manager.call_register_agent(self._path, "KeyboardDisplay")
        try:
            await manager.call_request_default_agent(self._path)
        except Exception:
            pass
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if not self._exported:
            return
        try:
            introspection = await self._bus.introspect("org.bluez", "/org/bluez")
            obj = self._bus.get_proxy_object("org.bluez", "/org/bluez", introspection)
            manager = obj.get_interface("org.bluez.AgentManager1")
            await manager.call_unregister_agent(self._path)
        except Exception:
            pass
        try:
            self._bus.unexport(self._path)
        except Exception:
            pass
