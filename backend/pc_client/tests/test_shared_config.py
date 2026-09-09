import json
from pathlib import Path
import unittest

from pc_client.protocol import (
    CONFIG,
    HEADER,
    HISTORY_CHUNK_PREFIX,
    HISTORY_RECORD,
    LAYOUT_STRUCTS,
    MAX_HISTORY_RECORDS_PER_CHUNK,
    Opcode,
    SHARED_PROTOCOL_DIRECTORY,
)
from protocol.generate_firmware_config import (
    generate_header,
    load_and_validate,
    validate_pairing_passkey,
)


SHARED_CONFIG = SHARED_PROTOCOL_DIRECTORY / "thermometer_protocol.json"


class SharedConfigTests(unittest.TestCase):
    def test_shared_protocol_is_the_monorepo_sibling(self) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        self.assertEqual(SHARED_PROTOCOL_DIRECTORY, repository_root / "protocol")
        firmware_cmake = (repository_root / "firmware" / "main" / "CMakeLists.txt")
        cmake_text = firmware_cmake.read_text(encoding="utf-8")
        self.assertIn(
            "${THERMOMETER_PROTOCOL_DIR}/thermometer_protocol.json", cmake_text
        )
        self.assertIn(
            'file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/generated")', cmake_text
        )

    def test_vscode_workspace_selects_the_firmware_project(self) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        workspace = json.loads(
            (repository_root / "ECE4880_Project1.code-workspace").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(workspace["folders"][0]["path"], "firmware")

        firmware_settings = json.loads(
            (repository_root / "firmware" / ".vscode" / "settings.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            firmware_settings["idf.buildPathWin"], "${workspaceFolder}\\build"
        )
        self.assertEqual(
            firmware_settings["idf.sdkconfigFilePath"],
            "${workspaceFolder}/sdkconfig",
        )

    def test_repository_ignores_credentials_and_generated_state(self) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        ignore_rules = {
            line.strip()
            for line in (repository_root / ".gitignore").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertIn("/backend/paired_devices.csv", ignore_rules)
        self.assertIn("/firmware/device_config.cmake", ignore_rules)
        self.assertIn("sdkconfig", ignore_rules)
        self.assertIn("**/build/", ignore_rules)

    def test_client_configuration_contains_only_active_settings(self) -> None:
        raw = load_and_validate(SHARED_CONFIG)

        self.assertEqual(
            set(raw["client"]),
            {
                "connect_timeout_seconds",
                "scan_timeout_seconds",
                "pairing_timeout_seconds",
                "use_cached_gatt_services",
            },
        )

    def test_json_drives_python_enums_and_layouts(self) -> None:
        raw = load_and_validate(SHARED_CONFIG)

        self.assertEqual(Opcode.GET_CURRENT, raw["protocol"]["opcodes"]["get_current"])
        self.assertEqual(
            HEADER.size,
            sum(
                {"u8": 1, "u16": 2, "u32": 4, "i16": 2}[field["type"]]
                for field in raw["protocol"]["layouts"]["header"]
            ),
        )
        self.assertEqual(set(LAYOUT_STRUCTS), set(raw["protocol"]["layouts"]))

    def test_service_configuration_is_central_and_loopback_only(self) -> None:
        raw = load_and_validate(SHARED_CONFIG)

        self.assertEqual(raw["service"]["api_host"], "127.0.0.1")
        self.assertEqual(raw["service"]["poll_interval_seconds"], 1.0)
        self.assertEqual(raw["service"]["history_chunk_retry_count"], 2)
        self.assertEqual(raw["service"]["persistence_queue_capacity"], 300)
        self.assertEqual(CONFIG.service.api_port, 8000)

    def test_generated_firmware_header_matches_python_sizes(self) -> None:
        raw = load_and_validate(SHARED_CONFIG)
        header = generate_header(raw, SHARED_CONFIG.name, "012345")

        self.assertIn(f"#define PROTOCOL_HEADER_SIZE {HEADER.size}U", header)
        self.assertIn(
            f"#define PROTOCOL_HISTORY_RECORD_SIZE {HISTORY_RECORD.size}U", header
        )
        expected_maximum_packet = (
            HEADER.size
            + HISTORY_CHUNK_PREFIX.size
            + MAX_HISTORY_RECORDS_PER_CHUNK * HISTORY_RECORD.size
        )
        self.assertIn(
            f"#define PROTOCOL_MAX_PACKET_SIZE {expected_maximum_packet}U", header
        )
        self.assertIn(
            '#define THERMOMETER_BLE_DEVICE_NAME_PREFIX "Thermometer-"', header
        )
        self.assertIn("#define THERMOMETER_BLE_PAIRING_PASSKEY 12345U", header)
        self.assertIn(
            '#define THERMOMETER_BLE_PAIRING_PASSKEY_TEXT "012345"', header
        )
        self.assertLessEqual(
            expected_maximum_packet, CONFIG.bluetooth.preferred_att_mtu - 1
        )

    def test_shared_json_contains_no_device_secret(self) -> None:
        raw = load_and_validate(SHARED_CONFIG)
        self.assertNotIn("pairing_passkey", raw["bluetooth"])
        self.assertNotIn("device_name", raw["bluetooth"])
        self.assertEqual(raw["protocol"]["version"], 2)

    def test_per_device_configuration_requires_six_digits(self) -> None:
        validate_pairing_passkey("012345")
        for passkey in ("", "12345", "12345x"):
            with self.subTest(passkey=passkey):
                with self.assertRaises(ValueError):
                    validate_pairing_passkey(passkey)


if __name__ == "__main__":
    unittest.main()
