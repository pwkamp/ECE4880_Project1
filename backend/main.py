"""Run the production localhost BLE connector service."""

from __future__ import annotations

import os

import uvicorn

from pc_client.protocol import CONFIG


def main() -> None:
    # One process must be the sole owner of the host BLE adapter/session.
    # Keep workers=1 and reload=False in production and development alike.
    uvicorn.run(
        "pc_client.service_api:create_app",
        factory=True,
        host=os.environ.get("THERMOMETER_API_HOST", CONFIG.service.api_host),
        port=int(os.environ.get("THERMOMETER_API_PORT", CONFIG.service.api_port)),
        workers=1,
        reload=False,
    )


if __name__ == "__main__":
    main()
