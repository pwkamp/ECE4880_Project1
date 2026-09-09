# Shared thermometer protocol

`thermometer_protocol.json` is the language-neutral source of truth consumed by
both `backend/pc_client` and the ESP-IDF project under `firmware/`.

Python validates and loads the JSON at process startup. Firmware does not parse
JSON at runtime: `firmware/main/CMakeLists.txt` runs
`generate_firmware_config.py` and produces
`firmware/build/generated/thermometer_config.h` as an explicit build output.

Keep this directory at the repository root beside `backend/` and `firmware/`.
For a standalone deployment, set `THERMOMETER_PROTOCOL_DIR` to this directory.

Protocol parity is tested from the repository root with:

```powershell
backend\.venv\Scripts\python.exe master_test.py
```

The test suite validates the JSON, Python packet layouts, opcodes and statuses,
then generates a temporary firmware header and compares its packet sizes and
constants with the Python implementation. A normal `idf.py build` separately
verifies the real firmware generation dependency.
