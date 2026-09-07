"""Small project-local registry for enrolled thermometer credentials.

The CSV intentionally stores plaintext credentials because that deployment
choice was requested.  It is ignored by source control and never exposed by
the REST API, but it is not a secure secret store.
"""

from __future__ import annotations

import csv
import os
import stat
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .protocol import CONFIG, validate_passkey


CSV_FIELDS = (
    "mac_address",
    "device_name",
    "pairing_passkey",
    "enrolled_at_utc",
    "last_connected_at_utc",
)


def default_registry_path() -> Path:
    """Return a path beside backend/main.py, independent of the current directory."""

    backend_root = Path(__file__).resolve().parents[1]
    return backend_root / CONFIG.service.credential_registry_filename


def normalize_mac_address(address: str) -> str:
    compact = "".join(character for character in address if character.isalnum())
    if len(compact) != 12:
        raise ValueError(f"invalid Bluetooth address: {address}")
    try:
        int(compact, 16)
    except ValueError as exc:
        raise ValueError(f"invalid Bluetooth address: {address}") from exc
    compact = compact.upper()
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


@dataclass(frozen=True)
class DeviceCredential:
    mac_address: str
    device_name: str
    pairing_passkey: str
    enrolled_at_utc: datetime
    last_connected_at_utc: datetime


class CredentialRegistry:
    """Thread-safe CSV reader/writer keyed by normalized Bluetooth address."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or default_registry_path()).resolve()
        self._lock = threading.RLock()
        self._records = self._read_all()

    def lookup(self, address: str) -> DeviceCredential | None:
        normalized = normalize_mac_address(address)
        with self._lock:
            return self._records.get(normalized)

    def save_verified(
        self,
        address: str,
        device_name: str,
        passkey: str,
        *,
        connected_at_utc: datetime | None = None,
    ) -> DeviceCredential:
        normalized = normalize_mac_address(address)
        credential = validate_passkey(passkey)
        observed_at = connected_at_utc or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            raise ValueError("connected_at_utc must be timezone-aware")

        with self._lock:
            existing = self._records.get(normalized)
            record = DeviceCredential(
                normalized,
                device_name,
                credential,
                existing.enrolled_at_utc if existing else observed_at,
                observed_at,
            )
            updated = dict(self._records)
            updated[normalized] = record
            self._write_all(updated)
            self._records = updated
            return record

    def delete(self, address: str) -> bool:
        normalized = normalize_mac_address(address)
        with self._lock:
            updated = dict(self._records)
            removed = updated.pop(normalized, None) is not None
            if removed:
                self._write_all(updated)
                self._records = updated
            return removed

    def _read_all(self) -> dict[str, DeviceCredential]:
        if not self.path.exists():
            return {}

        records: dict[str, DeviceCredential] = {}
        with self.path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if tuple(reader.fieldnames or ()) != CSV_FIELDS:
                raise ValueError(
                    f"credential registry has an invalid header: {self.path}"
                )
            for row_number, row in enumerate(reader, start=2):
                try:
                    normalized = normalize_mac_address(row["mac_address"])
                    passkey = validate_passkey(row["pairing_passkey"])
                    enrolled = datetime.fromisoformat(row["enrolled_at_utc"])
                    connected = datetime.fromisoformat(row["last_connected_at_utc"])
                    if enrolled.tzinfo is None or connected.tzinfo is None:
                        raise ValueError("timestamps must include a timezone")
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"credential registry row {row_number} is invalid"
                    ) from exc
                records[normalized] = DeviceCredential(
                    normalized,
                    row["device_name"],
                    passkey,
                    enrolled,
                    connected,
                )
        return records

    def _write_all(self, records: dict[str, DeviceCredential]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as csv_file:
                temporary_name = csv_file.name
                writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for address in sorted(records):
                    record = records[address]
                    writer.writerow(
                        {
                            "mac_address": record.mac_address,
                            "device_name": record.device_name,
                            "pairing_passkey": record.pairing_passkey,
                            "enrolled_at_utc": record.enrolled_at_utc.isoformat(),
                            "last_connected_at_utc": record.last_connected_at_utc.isoformat(),
                        }
                    )
                csv_file.flush()
                os.fsync(csv_file.fileno())
            os.chmod(temporary_name, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(temporary_name, self.path)
            temporary_name = None
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
