import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pc_client.credential_registry import (
    CSV_FIELDS,
    CredentialRegistry,
    default_registry_path,
    normalize_mac_address,
)


class CredentialRegistryTests(unittest.TestCase):
    def test_default_csv_is_beside_main(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        self.assertEqual(default_registry_path(), backend_root / "paired_devices.csv")
        self.assertTrue((backend_root / "main.py").exists())

    def test_verified_credentials_round_trip_and_preserve_leading_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.csv"
            registry = CredentialRegistry(path)
            observed = datetime(2026, 1, 2, tzinfo=timezone.utc)

            registry.save_verified(
                "aa-bb-cc-dd-ee-ff",
                "Thermometer-Test-01",
                "012345",
                connected_at_utc=observed,
            )
            stored = registry.lookup("AA:BB:CC:DD:EE:FF")

            self.assertIsNotNone(stored)
            self.assertEqual(stored.mac_address, "AA:BB:CC:DD:EE:FF")
            self.assertEqual(stored.pairing_passkey, "012345")
            with path.open("r", encoding="utf-8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))
            self.assertEqual(tuple(rows[0]), CSV_FIELDS)
            self.assertEqual(rows[0]["pairing_passkey"], "012345")

            self.assertTrue(registry.delete("aabbccddeeff"))
            self.assertIsNone(registry.lookup("AA:BB:CC:DD:EE:FF"))

    def test_rejects_invalid_address_and_passkey(self) -> None:
        self.assertRaises(ValueError, normalize_mac_address, "not-a-mac")
        with tempfile.TemporaryDirectory() as directory:
            registry = CredentialRegistry(Path(directory) / "devices.csv")
            with self.assertRaises(ValueError):
                registry.save_verified(
                    "AA:BB:CC:DD:EE:FF", "Thermometer", "12345"
                )


if __name__ == "__main__":
    unittest.main()
