# Thermometer backend

This directory contains the reusable `pc_client` package, the production
localhost REST service in `main.py`, and the gitignored per-PC credential
registry. It consumes the repository-level `../protocol` definition.

## Install and run

Python 3.10 or newer and Windows 10/11 are required for the automatic BLE PIN
pairing implementation. From this directory:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r pc_client\requirements.txt
.venv\Scripts\python.exe main.py
```

The REST service listens on `127.0.0.1:8000`. Run the Tk hardware test tool
with:

```powershell
.venv\Scripts\python.exe -m pc_client.gui
```

`paired_devices.csv` is created beside `main.py` after successful enrollment.
It contains plaintext per-device credentials and is explicitly excluded by the
root `.gitignore`.

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
