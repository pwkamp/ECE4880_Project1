"""Run the real backend HTTP API against a simulated thermometer.

For demoing/testing the full chain (frontend <-> backend API <-> MySQL) when
no ESP32 hardware is available. Serves the exact same REST API as main.py,
on the same host/port -- the frontend needs zero reconfiguration. Swap this
in for `python main.py` only; everything else (frontend/run.ps1, Vite,
the Node sample reader) runs unchanged.

    python -m pc_client.mock_server
"""

from __future__ import annotations

import os

import uvicorn

from .ble_service import ThermometerBleService
from .database_adapter import load_database_adapter
from .mock_run import MOCK_DEVICE, MOCK_PASSKEY, MockBleClient, _InMemoryCredentials, _discover
from .protocol import CONFIG
from .service_api import create_app


def main() -> None:
    credentials = _InMemoryCredentials()
    credentials.enroll(MOCK_DEVICE.address, MOCK_PASSKEY, MOCK_DEVICE.name)

    service = ThermometerBleService(
        database=load_database_adapter(),
        client_factory=MockBleClient,
        discover=_discover,
        auto_discover_on_start=True,
        credential_registry=credentials,
    )

    app = create_app(service=service)
    uvicorn.run(
        app,
        host=os.environ.get("THERMOMETER_API_HOST", CONFIG.service.api_host),
        port=int(os.environ.get("THERMOMETER_API_PORT", CONFIG.service.api_port)),
        workers=1,
        reload=False,
    )


if __name__ == "__main__":
    main()
