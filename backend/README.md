# Thermometer backend

This directory contains the reusable `pc_client` package, the production
localhost REST service in `main.py`, the MySQL adapter, and the gitignored
per-PC credential registry. It consumes the repository-level `../protocol`
definition.

## Full integration on Windows and Linux

MySQL runs in Docker on both platforms. On Windows, this service runs natively
and Bleak uses WinRT with the PC's built-in Bluetooth adapter. On Linux, the
service runs in the `linux` Compose profile and reaches host BlueZ through the
system D-Bus socket. Neither path needs a dedicated dongle or USB/IP.

From the repository root, use the launcher for the host OS:

```powershell
.\backend\run.ps1
```

```bash
bash backend/run.sh
```

On its first run, the script copies `backend/.env.example` to the gitignored
`backend/.env`. That file is the single configuration source for both host
paths. Each backend start intentionally runs `docker compose down
--volumes`, recreates the MySQL schema, waits for MySQL to become healthy, and
then starts the BLE API on <http://127.0.0.1:8000>.
To restart the backend without deleting recorded samples, stop its running
terminal and use `backend/run.ps1 -KeepDatabase` on Windows or
`bash backend/run.sh --keep-db` on Linux. The default remains a clean reset.

If an old or damaged OS bond prevents GATT service discovery, stop the backend
and explicitly clear every thermometer enrolled by this project before
starting it again:

```powershell
.\backend\run.ps1 -KeepDatabase -ResetPairings
```

```bash
bash backend/run.sh --keep-db --reset-pairings
```

This does not touch unrelated Bluetooth devices. It removes each enrolled
thermometer from WinRT/BlueZ and from `.runtime/paired_devices.csv`, so the web
console will request the six-digit PIN again. Firmware accepts this explicit
recovery as a fresh authenticated pairing; flash the current firmware before
using the reset option with builds that rejected all repeat pairing.

On Linux, the backend container connects to host BlueZ through
`/run/dbus/system_bus_socket`; it is not privileged and does not receive the
host HCI device directly. On Windows, `run.ps1` prepares `backend/.venv` and
runs `main.py` natively. Enrollment data on both systems is stored under the
gitignored `backend/.runtime/`, separately from the reset database.

Start the matching frontend launcher from a second terminal. The complete
setup and acceptance checklist is in
[`docs/integration-test.md`](../docs/integration-test.md).

## Install and run

Python 3.10 or newer. The same `main.py` detects the OS (`sys.platform`) and
selects WinRT PIN pairing on Windows 10/11 or BlueZ (D-Bus agent) on Linux.
Linux **does not auto-scan on startup** - use the web console Scan/Connect
buttons. Your user must be in the `bluetooth` group (`groups` should list it
after a full log-out). From this directory:

Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r pc_client\requirements.txt
.venv\Scripts\python.exe main.py
```

Linux:

```bash
python3 -m venv .venv
.venv/bin/pip install -r pc_client/requirements.txt
.venv/bin/python main.py
```

The REST service listens on `127.0.0.1:8000`. `GET /api/v1/ble/status` reports
`host_os` (`windows` or `linux`) and `pairing_backend` (`winrt` or `bluez`).
Full Scan → PIN → Connect steps, adapter setup, and troubleshooting live in
the repository root README section **Connecting the console to BLE and MySQL**.

Run the Tk hardware test tool with:

```powershell
.venv\Scripts\python.exe -m pc_client.gui
```

```bash
.venv/bin/python -m pc_client.gui
```

For a manual native start, `paired_devices.csv` is created beside `main.py`
after successful enrollment. It contains plaintext per-device credentials and
is excluded from Git. Both integration launchers instead use
`THERMOMETER_CREDENTIAL_REGISTRY_PATH` to keep the same file under persistent,
gitignored `backend/.runtime/`.

To persist samples, set
`THERMOMETER_DATABASE_ADAPTER_FACTORY=pc_client.mysql_adapter:create_adapter`
plus `THERMOMETER_DB_*` (see `backend/database/README.md`).

`THERMOMETER_API_HOST` and `THERMOMETER_API_PORT` can override the default
loopback endpoint. The Linux container binds `0.0.0.0` internally but publishes
the service only on host loopback. `THERMOMETER_CORS_ORIGINS` enables an exact,
loopback-only browser allowlist for the Windows frontend and is disabled by
default.

## Tests

The development requirements include the runtime dependencies and API test
client. From the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\pc_client\requirements-dev.txt
backend\.venv\Scripts\python.exe master_test.py
```

`master_test.py` discovers every `test_*.py` below `backend/pc_client/tests`
and exits nonzero for import, setup, or test failures. No ESP32 or Bluetooth
adapter is required for these unit tests. See the repository README for the
API, enrollment, database-adapter, and firmware-test details.
