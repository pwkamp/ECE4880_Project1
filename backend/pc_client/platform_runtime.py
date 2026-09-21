"""OS-specific production defaults for the BLE connector service.

The same Python package runs on Windows and Linux. Pairing backends and
scan policy are chosen from ``sys.platform`` - never from a config flag
the operator has to remember.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass, replace
from os import environ as os_environ
from typing import Any

from .protocol import CONFIG, ServiceConfig


@dataclass(frozen=True)
class BleHostRuntime:
    """Detected host BLE policy for the connector process."""

    family: str
    pairing: str
    auto_discover_on_start: bool


def detect_ble_host(
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
) -> BleHostRuntime:
    """Return Windows/WinRT, Linux/BlueZ, or a conservative fallback."""

    platform_name = (sys.platform if platform is None else platform).lower()
    environ = os_environ if env is None else env
    if platform_name in {"win32", "windows", "cygwin"} or platform_name.startswith(
        "win"
    ):
        return BleHostRuntime("windows", "winrt", True)
    if platform_name.startswith("linux"):
        auto_discover = str(environ.get("THERMOMETER_LINUX_AUTO_SCAN", "")).strip() == "1"
        return BleHostRuntime("linux", "bluez", auto_discover)
    return BleHostRuntime("other", "none", True)


def production_service_kwargs(
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Constructor kwargs for :class:`ThermometerBleService` in ``main.py``.

    Linux must not auto-scan on a 2 s loop: that pattern wedges BlueZ on many
    laptops. Manual Scan/Connect from the console still works. Set
    ``THERMOMETER_LINUX_AUTO_SCAN=1`` to restore Windows-style probing.
    """

    host = detect_ble_host(platform, env)
    settings: ServiceConfig = CONFIG.service
    if host.family == "linux":
        settings = replace(
            CONFIG.service,
            auto_discovery_interval_seconds=max(
                CONFIG.service.auto_discovery_interval_seconds, 15.0
            ),
            startup_scan_timeout_seconds=min(
                max(CONFIG.service.startup_scan_timeout_seconds, 3.0), 5.0
            ),
        )
    return {
        "auto_discover_on_start": host.auto_discover_on_start,
        "settings": settings,
    }
