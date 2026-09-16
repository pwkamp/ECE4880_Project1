# Thermometer backend

This directory contains the reusable `pc_client` package, the production
localhost REST service in `main.py`, the MySQL adapter, and the gitignored
per-PC credential registry. It consumes the repository-level `../protocol`
definition.

## Install and run

Python 3.10 or newer. The same `main.py` detects the OS (`sys.platform`) and
selects WinRT PIN pairing on Windows 10/11 or BlueZ (D-Bus agent) on Linux.
Linux **does not auto-scan on startup** — use the web console Scan/Connect
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

`paired_devices.csv` is created beside `main.py` after successful enrollment.
It contains plaintext per-device credentials and is explicitly excluded by the
root `.gitignore`.

To persist samples, set
`THERMOMETER_DATABASE_ADAPTER_FACTORY=pc_client.mysql_adapter:create_adapter`
plus `THERMOMETER_DB_*` (see `backend/database/README.md`).

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
