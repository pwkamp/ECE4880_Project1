from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pc_client.windows_pairing import (
    DevicePairingKinds,
    DevicePairingProtectionLevel,
    DevicePairingResultStatus,
    DeviceUnpairingResultStatus,
)

from pc_client import windows_pairing


class _PairingRequest:
    pairing_kind = DevicePairingKinds.PROVIDE_PIN

    def __init__(self) -> None:
        self.accepted_pin: str | None = None

    def accept_with_pin(self, pin: str) -> None:
        self.accepted_pin = pin


class _CustomPairing:
    def __init__(self, pairing: "_Pairing") -> None:
        self.pairing = pairing
        self.handler = None
        self.removed_token = None
        self.accepted_pin: str | None = None
        self.requested_kind = None
        self.requested_protection = None
        self.result_status = DevicePairingResultStatus.PAIRED
        self.invoke_handler = True

    def add_pairing_requested(self, handler: object) -> int:
        self.handler = handler
        return 123

    def remove_pairing_requested(self, token: int) -> None:
        self.removed_token = token

    async def pair_with_protection_level_async(
        self, pairing_kind: object, protection: object
    ) -> object:
        self.requested_kind = pairing_kind
        self.requested_protection = protection
        if self.invoke_handler:
            request = _PairingRequest()
            self.handler(self, request)
            self.accepted_pin = request.accepted_pin
        if self.result_status == DevicePairingResultStatus.PAIRED:
            self.pairing.is_paired = True
            self.pairing.protection_level = (
                DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION
            )
        return SimpleNamespace(status=self.result_status)


class _Pairing:
    def __init__(self, *, paired: bool = False) -> None:
        self.is_paired = paired
        self.can_pair = not paired
        self.protection_level = (
            DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION
            if paired
            else DevicePairingProtectionLevel.DEFAULT
        )
        self.custom = _CustomPairing(self)
        self.unpair_count = 0

    async def unpair_async(self) -> object:
        self.unpair_count += 1
        self.is_paired = False
        return SimpleNamespace(status=DeviceUnpairingResultStatus.UNPAIRED)


class _Endpoint:
    def __init__(self, identifier: str, address: str, *, paired: bool = False) -> None:
        self.id = identifier
        self.address = address
        self.pairing = _Pairing(paired=paired)


class _DeviceInformationApi:
    endpoints: list[_Endpoint] = []

    @classmethod
    async def create_from_id_async(cls, identifier: str) -> _Endpoint:
        return next(endpoint for endpoint in cls.endpoints if endpoint.id == identifier)


class _BluetoothDeviceHandle:
    def __init__(self, endpoint: _Endpoint) -> None:
        self.device_information = SimpleNamespace(id=endpoint.id)
        self.closed = False
        self.close_error: OSError | None = None

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _BluetoothDeviceApi:
    endpoints: list[_Endpoint] = []
    requested_address: int | None = None
    last_handle: _BluetoothDeviceHandle | None = None

    @classmethod
    async def from_bluetooth_address_async(
        cls, address: int
    ) -> _BluetoothDeviceHandle | None:
        cls.requested_address = address
        for endpoint in cls.endpoints:
            compact = "".join(
                character for character in endpoint.address if character.isalnum()
            )
            if int(compact, 16) == address:
                cls.last_handle = _BluetoothDeviceHandle(endpoint)
                return cls.last_handle
        return None


class WindowsPairingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _DeviceInformationApi.endpoints = []
        _BluetoothDeviceApi.endpoints = []
        _BluetoothDeviceApi.requested_address = None
        _BluetoothDeviceApi.last_handle = None

    async def test_resolves_address_and_injects_zero_padded_passkey(self) -> None:
        other = _Endpoint("other", "11:22:33:44:55:66")
        target = _Endpoint("target", "AA-BB-CC-DD-EE-FF")
        _DeviceInformationApi.endpoints = [other, target]
        _BluetoothDeviceApi.endpoints = [other, target]

        with (
            patch.object(windows_pairing, "DeviceInformation", _DeviceInformationApi),
            patch.object(windows_pairing, "BluetoothLEDevice", _BluetoothDeviceApi),
        ):
            await windows_pairing.pair_device("aa:bb:cc:dd:ee:ff", "000042", 1.0)

        custom = target.pairing.custom
        self.assertEqual(custom.accepted_pin, "000042")
        self.assertEqual(custom.requested_kind, DevicePairingKinds.PROVIDE_PIN)
        self.assertEqual(
            custom.requested_protection,
            DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION,
        )
        self.assertEqual(custom.removed_token, 123)
        self.assertEqual(_BluetoothDeviceApi.requested_address, 0xAABBCCDDEEFF)
        self.assertTrue(_BluetoothDeviceApi.last_handle.closed)

    async def test_reuses_existing_authenticated_bond(self) -> None:
        target = _Endpoint("target", "AA:BB:CC:DD:EE:FF", paired=True)
        _DeviceInformationApi.endpoints = [target]
        _BluetoothDeviceApi.endpoints = [target]

        with (
            patch.object(windows_pairing, "DeviceInformation", _DeviceInformationApi),
            patch.object(windows_pairing, "BluetoothLEDevice", _BluetoothDeviceApi),
        ):
            await windows_pairing.pair_device("AA:BB:CC:DD:EE:FF", "123456", 1.0)

        self.assertIsNone(target.pairing.custom.requested_kind)

    async def test_cleanup_error_does_not_hide_successful_pairing(self) -> None:
        target = _Endpoint("target", "AA:BB:CC:DD:EE:FF")
        _DeviceInformationApi.endpoints = [target]
        _BluetoothDeviceApi.endpoints = [target]

        original_open = _BluetoothDeviceApi.from_bluetooth_address_async

        async def open_with_failing_close(address: int) -> _BluetoothDeviceHandle:
            handle = await original_open(address)
            assert handle is not None
            handle.close_error = OSError(-2147024874, "bad command")
            return handle

        with (
            patch.object(windows_pairing, "DeviceInformation", _DeviceInformationApi),
            patch.object(
                windows_pairing,
                "BluetoothLEDevice",
                SimpleNamespace(
                    from_bluetooth_address_async=open_with_failing_close
                ),
            ),
        ):
            await windows_pairing.pair_device(
                "AA:BB:CC:DD:EE:FF", "123456", 1.0
            )

        self.assertTrue(target.pairing.is_paired)

    async def test_pairing_failure_reports_status_and_removes_handler(self) -> None:
        target = _Endpoint("target", "AA:BB:CC:DD:EE:FF")
        target.pairing.custom.result_status = DevicePairingResultStatus.FAILED
        target.pairing.custom.invoke_handler = False
        _DeviceInformationApi.endpoints = [target]
        _BluetoothDeviceApi.endpoints = [target]

        with (
            patch.object(windows_pairing, "DeviceInformation", _DeviceInformationApi),
            patch.object(windows_pairing, "BluetoothLEDevice", _BluetoothDeviceApi),
        ):
            with self.assertRaisesRegex(
                windows_pairing.WindowsPairingError,
                r"FAILED \(ceremonies: none\)",
            ):
                await windows_pairing.pair_device(
                    "AA:BB:CC:DD:EE:FF", "123456", 1.0
                )

        self.assertEqual(target.pairing.custom.removed_token, 123)

    async def test_forget_device_explicitly_removes_bond(self) -> None:
        target = _Endpoint("target", "AA:BB:CC:DD:EE:FF", paired=True)
        _DeviceInformationApi.endpoints = [target]
        _BluetoothDeviceApi.endpoints = [target]

        with (
            patch.object(windows_pairing, "DeviceInformation", _DeviceInformationApi),
            patch.object(windows_pairing, "BluetoothLEDevice", _BluetoothDeviceApi),
        ):
            await windows_pairing.forget_device("AA:BB:CC:DD:EE:FF")

        self.assertEqual(target.pairing.unpair_count, 1)
        self.assertFalse(target.pairing.is_paired)


if __name__ == "__main__":
    unittest.main()
