"""Explicitly remove every thermometer pairing owned by this project.

This is intentionally a launcher-only recovery tool.  It is never called by
normal backend startup, and it limits itself to addresses in the project's
credential registry so headphones and other Windows/BlueZ devices are not
touched.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Sequence
import sys

from .credential_registry import CredentialRegistry, DeviceCredential
from .platform_runtime import detect_ble_host


ForgetDevice = Callable[[str], Awaitable[None]]


def _forgetter() -> ForgetDevice:
    host = detect_ble_host()
    if host.pairing == "winrt":
        from .windows_pairing import forget_device

        return forget_device
    if host.pairing == "bluez":
        from .linux_pairing import forget_device

        return forget_device
    raise RuntimeError(f"pairing reset is not supported on {host.family}")


async def reset_all_pairings(
    registry: CredentialRegistry,
    *,
    forget: ForgetDevice | None = None,
) -> tuple[DeviceCredential, ...]:
    """Unpair and delete all enrolled thermometers.

    A credential is deleted only after its operating-system bond was removed.
    Keeping a failed entry makes the problem visible and permits a later retry.
    """

    records = registry.list_all()
    remove = forget or _forgetter()
    failures: list[str] = []
    for record in records:
        try:
            await remove(record.mac_address)
        except Exception as exc:
            detail = str(exc).strip() or type(exc).__name__
            failures.append(f"{record.device_name} ({record.mac_address}): {detail}")
            continue
        registry.delete(record.mac_address)

    if failures:
        raise RuntimeError(
            "could not remove every thermometer bond:\n- " + "\n- ".join(failures)
        )
    return records


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove all OS bonds and saved credentials for enrolled thermometers."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="required safety flag confirming that every enrolled thermometer is reset",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.all:
        _parser().error("--all is required")

    registry = CredentialRegistry()
    records = registry.list_all()
    if not records:
        print("No enrolled thermometer pairings were found.")
        return 0

    try:
        removed = asyncio.run(reset_all_pairings(registry))
    except Exception as exc:
        print(f"Pairing reset failed: {exc}", file=sys.stderr)
        return 1

    print(f"Removed {len(removed)} thermometer pairing(s) from the OS and registry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
