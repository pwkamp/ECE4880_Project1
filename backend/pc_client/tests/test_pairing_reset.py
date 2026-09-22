import tempfile
from pathlib import Path
import unittest

from pc_client.credential_registry import CredentialRegistry
from pc_client.pairing_reset import reset_all_pairings


class PairingResetTests(unittest.IsolatedAsyncioTestCase):
    def make_registry(self, directory: str) -> CredentialRegistry:
        registry = CredentialRegistry(Path(directory) / "paired.csv")
        registry.save_verified(
            "AA:BB:CC:DD:EE:01", "Thermometer-One", "123456"
        )
        registry.save_verified(
            "AA:BB:CC:DD:EE:02", "Thermometer-Two", "654321"
        )
        return registry

    async def test_removes_os_bonds_before_registry_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = self.make_registry(directory)
            calls: list[str] = []

            async def forget(address: str) -> None:
                self.assertIsNotNone(registry.lookup(address))
                calls.append(address)

            removed = await reset_all_pairings(registry, forget=forget)

            self.assertEqual(len(removed), 2)
            self.assertEqual(
                calls, ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
            )
            self.assertEqual(registry.list_all(), ())

    async def test_keeps_failed_entry_for_a_safe_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = self.make_registry(directory)

            async def forget(address: str) -> None:
                if address.endswith("01"):
                    raise OSError("radio refused removal")

            with self.assertRaisesRegex(RuntimeError, "radio refused removal"):
                await reset_all_pairings(registry, forget=forget)

            self.assertIsNotNone(registry.lookup("AA:BB:CC:DD:EE:01"))
            self.assertIsNone(registry.lookup("AA:BB:CC:DD:EE:02"))


if __name__ == "__main__":
    unittest.main()
