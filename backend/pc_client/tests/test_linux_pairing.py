import unittest
from unittest.mock import AsyncMock, patch

from pc_client.linux_pairing import (
    LinuxPairingError,
    device_object_path,
    forget_device,
    normalize_address,
    pair_device,
)
from pc_client.platform_runtime import detect_ble_host, production_service_kwargs
from pc_client.protocol import CONFIG


class _FakeBlueZ:
    def __init__(self) -> None:
        self.paired: set[str] = set()
        self.pair_calls: list[tuple[str, str, float]] = []
        self.removed: list[str] = []

    async def is_paired(self, address: str) -> bool:
        return address.upper() in self.paired

    async def pair(self, address: str, passkey: str, timeout: float) -> None:
        self.pair_calls.append((address, passkey, timeout))
        self.paired.add(address.upper())

    async def remove(self, address: str) -> None:
        self.removed.append(address)
        self.paired.discard(address.upper())


class LinuxPairingTests(unittest.IsolatedAsyncioTestCase):
    def test_normalize_address_and_object_path(self) -> None:
        self.assertEqual(normalize_address("aa:bb:cc:dd:ee:ff"), "AA:BB:CC:DD:EE:FF")
        self.assertEqual(
            device_object_path("/org/bluez/hci0", "AA:BB:CC:DD:EE:FF"),
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
        )
        with self.assertRaises(LinuxPairingError):
            normalize_address("not-a-mac")

    async def test_pair_device_supplies_passkey_when_not_already_bonded(self) -> None:
        bluez = _FakeBlueZ()
        await pair_device("aa:bb:cc:dd:ee:ff", "123456", 5.0, backend=bluez)
        self.assertEqual(bluez.pair_calls, [("AA:BB:CC:DD:EE:FF", "123456", 5.0)])
        self.assertIn("AA:BB:CC:DD:EE:FF", bluez.paired)

    async def test_pair_device_skips_bluez_when_already_paired(self) -> None:
        bluez = _FakeBlueZ()
        bluez.paired.add("AA:BB:CC:DD:EE:FF")
        await pair_device("AA:BB:CC:DD:EE:FF", "123456", 5.0, backend=bluez)
        self.assertEqual(bluez.pair_calls, [])

    async def test_pair_device_rejects_a_bad_passkey(self) -> None:
        with self.assertRaises(ValueError):
            await pair_device("AA:BB:CC:DD:EE:FF", "12", 5.0, backend=_FakeBlueZ())

    async def test_forget_device_removes_the_bluez_bond(self) -> None:
        bluez = _FakeBlueZ()
        bluez.paired.add("AA:BB:CC:DD:EE:FF")
        await forget_device("aa:bb:cc:dd:ee:ff", backend=bluez)
        self.assertEqual(bluez.removed, ["AA:BB:CC:DD:EE:FF"])
        self.assertNotIn("AA:BB:CC:DD:EE:FF", bluez.paired)


class PlatformRuntimeTests(unittest.TestCase):
    def test_windows_host_uses_winrt_and_auto_scan(self) -> None:
        host = detect_ble_host("win32", {})
        self.assertEqual(host.family, "windows")
        self.assertEqual(host.pairing, "winrt")
        self.assertTrue(host.auto_discover_on_start)
        self.assertEqual(detect_ble_host("windows", {}).family, "windows")

    def test_linux_host_uses_bluez_and_manual_scan(self) -> None:
        host = detect_ble_host("linux", {})
        self.assertEqual(host.family, "linux")
        self.assertEqual(host.pairing, "bluez")
        self.assertFalse(host.auto_discover_on_start)

    def test_unknown_host_does_not_claim_a_pairing_backend(self) -> None:
        host = detect_ble_host("darwin", {})
        self.assertEqual(host.family, "other")
        self.assertEqual(host.pairing, "none")

    def test_linux_production_does_not_auto_scan(self) -> None:
        options = production_service_kwargs("linux", {})
        self.assertFalse(options["auto_discover_on_start"])
        self.assertGreaterEqual(
            options["settings"].auto_discovery_interval_seconds, 15.0
        )

    def test_linux_auto_scan_can_be_opted_into(self) -> None:
        options = production_service_kwargs(
            "linux", {"THERMOMETER_LINUX_AUTO_SCAN": "1"}
        )
        self.assertTrue(options["auto_discover_on_start"])

    def test_windows_keeps_automatic_discovery(self) -> None:
        options = production_service_kwargs("win32", {})
        self.assertTrue(options["auto_discover_on_start"])
        self.assertEqual(
            options["settings"].auto_discovery_interval_seconds,
            CONFIG.service.auto_discovery_interval_seconds,
        )
        self.assertGreaterEqual(
            options["settings"].recovery_deadline_seconds,
            CONFIG.client.connect_timeout_seconds + 5.0,
        )


if __name__ == "__main__":
    unittest.main()
