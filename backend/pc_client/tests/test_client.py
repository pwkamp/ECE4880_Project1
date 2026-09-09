import asyncio
import struct
import unittest
from unittest.mock import AsyncMock, patch

from pc_client.protocol import (
    CONFIG,
    CurrentSnapshot,
    HEADER,
    PROTOCOL_VERSION,
    ProtocolError,
    RESPONSE_FLAG,
    REQUEST_CHARACTERISTIC_UUID,
    RESPONSE_CHARACTERISTIC_UUID,
    SERVICE_UUID,
    Opcode,
    Status,
    VisibleState,
)
from pc_client.thermometer_client import ThermometerBleClient, describe_ble_error

TEST_PASSKEY = "123456"


class _FakeServices:
    @staticmethod
    def get_service(_uuid: str) -> object:
        return object()


class _FakeBleakClient:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.is_connected = False
        self.services = _FakeServices()
        self.mtu_size = 247
        self.operations: list[str] = []
        self.response = b""
        self.display = [False, False]
        self.fail_next_write = False
        self.disconnected_callback = _kwargs.get("disconnected_callback")

    async def connect(self) -> None:
        self.operations.append("connect")
        self.is_connected = True

    async def disconnect(self) -> None:
        self.operations.append("disconnect")
        self.is_connected = False

    async def write_gatt_char(self, uuid: str, packet: bytes, response: bool) -> None:
        self.operations.append("write")
        if self.fail_next_write:
            self.fail_next_write = False
            raise OSError()
        assert uuid == REQUEST_CHARACTERISTIC_UUID
        assert response
        version, opcode, request_id, length, status, flags = HEADER.unpack_from(packet)
        assert version == PROTOCOL_VERSION and status == 0 and flags == 0
        payload = packet[8:]
        assert len(payload) == length

        if opcode == Opcode.GET_CURRENT:
            result = struct.pack(
                "<IIhBBhBBhBB",
                99,
                12,
                2000,
                VisibleState.OFF,
                self.display[0],
                2200,
                VisibleState.ON if self.display[1] else VisibleState.OFF,
                self.display[1],
                0,
                0,
                0,
            )
        elif opcode == Opcode.SET_DISPLAY:
            sensor_id, enabled = payload
            self.display[sensor_id - 1] = bool(enabled)
            result = bytes(
                (sensor_id, VisibleState.ON if enabled else VisibleState.OFF, enabled)
            )
        elif opcode == Opcode.AUTH_BEGIN:
            result = struct.pack(
                "<6sI16s", bytes.fromhex("AABBCCDDEEFF"), 99, bytes(16)
            )
        elif opcode == Opcode.AUTH_PROVE:
            assert len(payload) == 32
            result = b""
        else:
            raise AssertionError(f"unexpected opcode {opcode}")
        self.response = HEADER.pack(
            PROTOCOL_VERSION,
            opcode,
            request_id,
            len(result),
            Status.SUCCESS,
            RESPONSE_FLAG,
        ) + result

    async def read_gatt_char(self, uuid: str) -> bytes:
        self.operations.append("read")
        assert uuid == RESPONSE_CHARACTERISTIC_UUID
        return self.response


class _PausedWriteBleakClient(_FakeBleakClient):
    """Lets a test request teardown in the middle of a transaction."""

    def __init__(self) -> None:
        super().__init__()
        self.write_started = asyncio.Event()
        self.resume_write = asyncio.Event()

    async def write_gatt_char(self, uuid: str, packet: bytes, response: bool) -> None:
        self.write_started.set()
        await self.resume_write.wait()
        await super().write_gatt_char(uuid, packet, response)


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def test_blank_platform_error_gets_a_useful_name(self) -> None:
        self.assertEqual(describe_ble_error(OSError()), "OSError")

    async def test_connection_uses_stock_bleak_without_implicit_pairing(self) -> None:
        captured_options: dict[str, object] = {}
        fake = _FakeBleakClient()

        def make_client(*_args: object, **options: object) -> _FakeBleakClient:
            captured_options.update(options)
            return fake

        client = ThermometerBleClient(
            "fake", client_factory=make_client, passkey=TEST_PASSKEY
        )
        await client.connect(authenticate=False)

        self.assertFalse(captured_options["pair"])
        self.assertNotIn("services", captured_options)
        self.assertNotIn("backend", captured_options)
        self.assertEqual(fake.operations, ["connect"])
        await client.close()

    async def test_public_pair_uses_central_passkey_and_timeout(self) -> None:
        fake = _FakeBleakClient()
        client = ThermometerBleClient(
            "AA:BB:CC:DD:EE:FF",
            client_factory=lambda *_a, **_k: fake,
            passkey=TEST_PASSKEY,
        )
        pair_device = AsyncMock()

        with (
            patch.object(client, "_uses_native_windows_client", return_value=True),
            patch("pc_client.windows_pairing.pair_device", pair_device),
        ):
            await client.pair("000042")

        pair_device.assert_awaited_once_with(
            "AA:BB:CC:DD:EE:FF",
            "000042",
            CONFIG.client.pairing_timeout_seconds,
        )

    async def test_public_forget_pairing_uses_explicit_windows_reset(self) -> None:
        fake = _FakeBleakClient()
        client = ThermometerBleClient(
            "AA:BB:CC:DD:EE:FF",
            client_factory=lambda *_a, **_k: fake,
            passkey=TEST_PASSKEY,
        )
        forget_device = AsyncMock()

        with (
            patch.object(client, "_uses_native_windows_client", return_value=True),
            patch("pc_client.windows_pairing.forget_device", forget_device),
        ):
            await client.forget_pairing()

        forget_device.assert_awaited_once_with("AA:BB:CC:DD:EE:FF")

    async def test_client_is_always_requester_and_controls_display(self) -> None:
        fake = _FakeBleakClient()
        client = ThermometerBleClient(
            "fake", client_factory=lambda *_a, **_k: fake, passkey=TEST_PASSKEY
        )

        await client.connect()
        current = await client.get_current()
        changed = await client.set_display(1, True)

        self.assertEqual(current.sensors[0].temperature_c, 20.0)
        self.assertTrue(changed.display_enabled)
        self.assertEqual(
            fake.operations,
            [
                "connect",
                "write",
                "read",
                "write",
                "read",
                "write",
                "read",
                "write",
                "read",
            ],
        )
        await client.close()

    async def test_failed_exchange_disconnects_without_hidden_retry(self) -> None:
        fake = _FakeBleakClient()
        client = ThermometerBleClient(
            "fake", client_factory=lambda *_a, **_k: fake, passkey=TEST_PASSKEY
        )
        await client.connect()
        fake.fail_next_write = True

        with self.assertRaisesRegex(RuntimeError, "GATT request write failed: OSError"):
            await client.get_current()

        self.assertEqual(
            fake.operations,
            [
                "connect",
                "write",
                "read",
                "write",
                "read",
                "write",
                "disconnect",
            ],
        )
        self.assertFalse(client.is_connected)

    async def test_disconnect_waits_for_complete_write_read_transaction(self) -> None:
        fake = _PausedWriteBleakClient()
        client = ThermometerBleClient(
            "fake", client_factory=lambda *_a, **_k: fake, passkey=TEST_PASSKEY
        )

        # Establish authentication first; this test isolates teardown during
        # one application request rather than during connection setup.
        fake.resume_write.set()
        await client.connect()
        fake.write_started = asyncio.Event()
        fake.resume_write = asyncio.Event()

        request = asyncio.create_task(client.get_current())
        await fake.write_started.wait()
        disconnect = asyncio.create_task(client.disconnect())
        await asyncio.sleep(0)

        self.assertFalse(disconnect.done())
        self.assertIs(client._client, fake)

        fake.resume_write.set()
        snapshot = await request
        await disconnect

        self.assertEqual(snapshot.sensors[0].temperature_c, 20.0)
        self.assertEqual(
            fake.operations,
            [
                "connect",
                "write",
                "read",
                "write",
                "read",
                "write",
                "read",
                "disconnect",
            ],
        )
        self.assertIsNone(client._client)

    async def test_physical_disconnect_retains_backend_until_cleanup(self) -> None:
        fake = _FakeBleakClient()
        disconnected = []

        def client_factory(*_args, **kwargs):
            fake.disconnected_callback = kwargs.get("disconnected_callback")
            return fake

        client = ThermometerBleClient(
            "fake",
            client_factory=client_factory,
            passkey=TEST_PASSKEY,
            disconnected_callback=lambda value: disconnected.append(value),
        )
        await client.connect(authenticate=False)

        fake.is_connected = False
        fake.disconnected_callback(fake)

        self.assertIs(client._client, fake)
        self.assertEqual(disconnected, [client])
        await client.disconnect()
        self.assertIsNone(client._client)
        self.assertEqual(fake.operations, ["connect", "disconnect"])

    async def test_chunk_size_adapts_to_mtu(self) -> None:
        fake = _FakeBleakClient()
        client = ThermometerBleClient(
            "fake", client_factory=lambda *_a, **_k: fake, passkey=TEST_PASSKEY
        )
        await client.connect(authenticate=False)
        self.assertEqual(client.records_per_chunk(), 32)
        fake.mtu_size = 23
        self.assertEqual(client.records_per_chunk(), 1)
        await client.close()

if __name__ == "__main__":
    unittest.main()
