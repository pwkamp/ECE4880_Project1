"""Run the production localhost BLE connector service."""

from __future__ import annotations

import uvicorn

from pc_client.protocol import CONFIG


def main() -> None:
    # One process must be the sole owner of the Windows BLE adapter/session.
    # Keep workers=1 and reload=False in production and development alike.
    uvicorn.run(
        "pc_client.service_api:create_app",
        factory=True,
        host=CONFIG.service.api_host,
        port=CONFIG.service.api_port,
        workers=1,
        reload=False,
    )


if __name__ == "__main__":
    main()
