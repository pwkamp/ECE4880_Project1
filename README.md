# ESP32 BLE Thermometer

This repository contains a request/response BLE thermometer implementation:

- ESP-IDF firmware for two independent temperature sensors
- deterministic fake sensor data and disconnect/recovery simulation
- two independent 300-record circular history buffers
- authenticated BLE pairing, bonding, encrypted GATT access, and protocol-level challenge-response
- a reusable async Python client library
- a production localhost BLE connector service with a REST API and database-adapter seam
- a Tk desktop GUI for live data, display control, history, and reconnects

The PC is always the application requester. The ESP32 never sends application notifications or indications. A client writes one request, then reads its matching response. This keeps unsolicited radio traffic out of the application protocol.

## Repository layout

This project uses the same top-level layout as `ECE4880_Project1`:

```text
backend/     Python BLE library, REST service, GUI, and unit tests
firmware/    Complete ESP-IDF project
protocol/    Shared JSON schema plus validation/header-generation tools
docs/        Architecture, traceability, and power-measurement notes
```

Neither consumer owns a private protocol copy. Python locates the sibling
`protocol/` directory independently of the current working directory, and
firmware CMake resolves the same sibling by default. Standalone deployments can
set `THERMOMETER_PROTOCOL_DIR` (environment variable for Python, CMake cache
path for firmware) without changing source files.

### VS Code and the ESP-IDF extension

Open [`ECE4880_Project1.code-workspace`](ECE4880_Project1.code-workspace) with
**File > Open Workspace from File**. The multi-root workspace makes
`firmware/` an actual VS Code workspace folder, which is required because the
ESP-IDF extension always uses its selected workspace folder as CMake's source
directory. If prompted, run **ESP-IDF: Pick a Workspace Folder** and select
`firmware`. The extension remembers that selection, after which its Build,
Flash, Monitor, Menuconfig, and Full Clean actions use `firmware/CMakeLists.txt`,
`firmware/build`, and `firmware/sdkconfig`.

Opening the repository root as a plain folder still works for general editing,
but the ESP-IDF Build button will treat that root as an IDF project and fail
because the root intentionally has no `CMakeLists.txt`. As a smaller
alternative, open `firmware/` directly in a separate VS Code window.

## Shared configuration

[protocol/thermometer_protocol.json](protocol/thermometer_protocol.json) is the single source for:

- protocol version, opcodes, statuses, flags, field order, types, and packet sizes
- UUIDs, device-name prefix, ATT MTU, advertising interval, and preferred connection interval
- sensor count, one-second sample period, history capacity, task sizing, and fault/recovery thresholds
- fake-sensor waveforms and disconnect windows
- PC scan/connect, GATT-cache policy, poll, reconnect, authentication, service, API, history-budget, and operation-retention settings

CMake validates the JSON and declares
[`protocol/generate_firmware_config.py`](protocol/generate_firmware_config.py)
as an explicit build dependency. The active firmware header is written to
`firmware/build/generated/thermometer_config.h`, and that generated directory is added
to the `main` component's include path. Both
[`firmware/main/include/protocol.h`](firmware/main/include/protocol.h) and
[`firmware/main/include/thermometer.h`](firmware/main/include/thermometer.h) include it. The
Python library loads the same JSON at runtime and constructs its packet
structures from those definitions. Change a protocol value once, rebuild and
reflash the ESP32, then restart the PC app. There is intentionally no
checked-in generated header or `.h.in` template to drift out of date.

Exact device names and credentials are deliberately absent from the shared JSON. Copy [firmware/device_config.cmake.example](firmware/device_config.cmake.example) to the gitignored `firmware/device_config.cmake`, then assign every ESP32 a unique six-digit passkey. `-DTHERMOMETER_PAIRING_PASSKEY=...` is accepted as an equivalent CMake cache argument. Configuration fails when it is missing or invalid. Firmware derives the advertised name as `Thermometer-XXXXXX` from the stable Bluetooth MAC suffix, so names are unique without a duplicated per-device setting. The passkey remains a usability-grade secret with only one million possible values; production hardware should additionally use Secure Boot and flash encryption.

## Firmware behavior

Each sensor has independent runtime state:

- signed centi-degrees Celsius as the canonical value
- connected/valid status
- display-enabled state
- latest one-second sample sequence

Each sensor has an independent acquisition task whose backend call waits for the next conversion. Results are sent to one state-owner task. A one-second state deadline snapshots the latest values into the two fixed 300-entry circular buffers and updates the display. Once full, the oldest record is overwritten. History is addressed by sequence number so a ring update cannot silently shift a client's requested position.

Periodic independent disconnects are enabled by default. A disconnect invalidates that sensor without disturbing the other sensor. On recovery, the sensor becomes valid again and its display is reset to disabled.

The two logical display states are independent. The current single GPIO LED is a physical stand-in: it is on when either valid sensor's display is enabled, and off when neither is visible. Both local controls and BLE commands use the same state-changing functions and render path.

The average is valid only while both sensors are connected and both displays are enabled.

Firmware modules:

- [thermometer.c](firmware/main/src/thermometer.c): sensor-event ownership, one-second snapshots, and display state
- [history_buffer.c](firmware/main/src/history_buffer.c): fixed circular-buffer operations
- [application_auth.c](firmware/main/src/application_auth.c): challenge, proof, expiry, and lockout state
- [protocol.c](firmware/main/src/protocol.c): packet validation and operation handlers
- [ble_server.c](firmware/main/src/ble_server.c): secure GATT service, pairing, advertising
- [temperature_sensors.h](firmware/main/include/temperature_sensors.h): sensor-backend interface
- [local_display.h](firmware/main/include/local_display.h): display-backend interface
- [local_controls.c](firmware/main/src/local_controls.c): local button/backlight integration stub

## Hardware backends

Sensor and display backends are selected independently under `Thermometer Configuration` in `idf.py menuconfig`. This allows any of these combinations:

- fake sensors + LED display simulator (default)
- real sensors + LED display simulator
- fake sensors + real LCD
- real sensors + real LCD

[fake_temperature_sensors.c](firmware/main/src/fake_temperature_sensors.c) and [led_display.c](firmware/main/src/led_display.c) are working implementations. [real_temperature_sensors.c](firmware/main/src/real_temperature_sensors.c) and [real_display.c](firmware/main/src/real_display.c) are compiling integration stubs with the required behavior documented at their handoff points. The Jira requirements do not select a sensor model, LCD bus, pinout, or display geometry, so those hardware choices are deliberately not invented here. Target defaults select a likely LED GPIO; confirm it for the actual board.

## Power behavior

The architecture is event driven except for the required one-second sample:

- Both acquisition tasks block inside their sensor backends, and the state-owner
  task blocks on its event queue until either a conversion completes or the
  one-second snapshot deadline arrives.
- FreeRTOS tickless idle and ESP-IDF dynamic frequency scaling are enabled.
- Bluetooth modem sleep is enabled, so the controller sleeps between advertising or connection events.
- advertising is intentionally slow (800-1000 ms), and the server requests a 200 ms connection interval with peripheral latency 1 after connection. The unique device name is in the primary advertisement so Windows can identify the device even when it omits scan-response data; the service UUID is in the scan response.
- the GATT server never sends notifications or indications. Protocol work happens only after the PC writes a request; the PC then reads the response.

On the original ESP32, the default Bluetooth low-power clock is the main crystal. ESP-IDF supports modem sleep and frequency scaling with that clock, but holds a lock that prevents automatic light sleep while Bluetooth is active. If the board actually has a 32.768 kHz crystal, selecting it as the Bluetooth/RTC low-power clock allows deeper BLE-preserving light sleep. Newer targets may support light sleep with their main crystal. This is a board clock decision, not something the application should guess.

Comments next to implementations cite relevant Jira requirement and SCRUM issue
IDs. [The traceability matrix](docs/requirements_traceability.md) distinguishes
implemented behavior, simulation support, integration stubs, and pending
hardware acceptance. Jira was used read-only; no issue fields or statuses are
changed by this project.

## Build and flash

Use an ESP-IDF 6.x terminal. On the first build, create the local device
configuration from its committed example:

```powershell
Set-Location firmware
if (-not (Test-Path device_config.cmake)) {
    Copy-Item device_config.cmake.example device_config.cmake
}
# Edit device_config.cmake with this ESP32's unique six-digit passkey.
idf.py set-target esp32
idf.py build
idf.py -p COM5 flash monitor
```

Replace `COM5` as needed. The original ESP32 is the only active firmware
target; defaults for other chips are not part of the active project. The app
binary is named `thermometer_gatt_server.bin`.
Changing a provisioned passkey does not authorize replacement of the existing
ESP32 bond. Use the authenticated reset API before changing it. If the owner
credential is lost, erase NVS or reflash/erase the device and remove its Windows
Bluetooth entry as a physical recovery procedure.

## Production Python connector service

Install the Python dependencies and start the single-process service:

```powershell
Set-Location backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r pc_client\requirements.txt
.venv\Scripts\python.exe main.py
```

The API listens only on `127.0.0.1:8000`. Uvicorn reload and multiple workers
are intentionally disabled because exactly one event loop/process must own the
Windows BLE session. CORS is not enabled: the authenticated web-server backend,
not browser JavaScript, is expected to call this localhost interface.

On startup the service repeatedly scans for compatible thermometers. With one
registered device, it autonomously pairs/connects, performs protocol
authentication, verifies the protocol version, reads the first protected
snapshot, and reaches `CONNECTED` with `ready=true`. One unregistered device
enters `AUTHENTICATION_REQUIRED`; multiple devices enter `SELECTION_REQUIRED`;
zero devices keep discovery active. An unexpected link failure retains the
target and retries every two seconds. An explicit `/api/v1/ble/disconnect`
disables retries without forgetting the in-memory target, and
`/api/v1/ble/reconnect` enables them again.

State transitions have one explicit owner and every device-dependent state has
a bounded exit:

| State | Trigger that advances it |
|---|---|
| `DISCOVERING` | A full BLE scan runs repeatedly; a completed manual scan is also consumed by the manager. Empty and failed scans schedule another probe. |
| `PAIRING` | Windows bond verification completes or reaches its configured timeout. |
| `CONNECTING` | GATT connection and service discovery complete or time out. |
| `VERIFYING` | Challenge-response and the initial protected temperature request complete or time out. |
| `CONNECTED` | The one-second request poll and Bleak callback independently detect connection loss. |
| `RECONNECTING` | Repeated scans must see the selected MAC again before a fresh GATT connection is attempted. |
| `AUTHENTICATION_REQUIRED`, `SELECTION_REQUIRED`, `DISCONNECTED` | An explicit API/GUI decision is required; these states do not guess user intent. |

Manager wake-ups carry a revision number, so a signal delivered while a state
update is being published cannot be cleared accidentally. Windows scanner,
connection, verification, and client-cleanup calls are also bounded, preventing
an operating-system Bluetooth call from leaving the state machine parked
indefinitely.

Successful enrollment is stored in `backend/paired_devices.csv` beside `backend/main.py`,
regardless of the process working directory. The file is atomically replaced,
preserves leading-zero passkeys, and is gitignored. It is intentionally
plaintext: anyone who can read the project directory can read its credentials.
No credential is saved until pairing, challenge verification, protocol
verification, and the initial protected temperature request all succeed.

The service publishes the first current snapshot before history recovery, polls
on absolute monotonic one-second boundaries, and stores unavailable boundaries
as provisional records without copying old temperatures forward. History is
requested metadata-first, recent-first, and round-robin between sensors. Each
chunk may be retried twice and the transfer returns/persists partial results at
the ten-second budget. Display requests have highest BLE priority, current polls
are next, and history chunks yield between requests.

REST endpoints:

| Method and path | Purpose |
|---|---|
| `GET /healthz` | Process/controller/database readiness |
| `GET /api/v1/ble/status` | Authoritative phase, transport/ready state, credential state, revision, target, retries, errors, and active operations |
| `POST /api/v1/ble/scan` | Filtered thermometer discovery while disconnected |
| `POST /api/v1/ble/connect` | Select an address and optionally supply a first-enrollment `passkey` |
| `POST /api/v1/ble/reconnect` | Re-enable the last in-memory target |
| `POST /api/v1/ble/disconnect` | Stop retries and cleanly disconnect |
| `POST /api/v1/ble/pair` | Enroll using `{address, passkey}` and remain connected |
| `DELETE /api/v1/ble/pairing/{address}` | Authenticated ESP32 reset, disconnect, Windows bond removal, then CSV removal |
| `GET /api/v1/ble/current` | Diagnostic cache; unavailable responses never contain stale numeric values |
| `PUT /api/v1/ble/displays/{sensor_id}` | Set and return the ESP32-confirmed display state |
| `POST /api/v1/ble/history/sync` | Begin one deduplicated tracked history operation |
| `GET /api/v1/operations/{operation_id}` | Inspect background progress, result, persistence, or structured error |

Connect, pair, pairing-reset, and history operations return HTTP `202`. A first
enrollment request needs a six-character string, for example
`{"address":"AA:BB:CC:DD:EE:FF","passkey":"012345"}`. Passkeys are never
returned in API responses or written to normal logs. Invalid
state transitions use `409`, invalid inputs `422`, unavailable BLE work `503`,
missing enrollment credentials use `401`, and a display confirmation timeout `504`. Interactive OpenAPI documentation is
available at `http://127.0.0.1:8000/docs`.

### Database integration

[database_adapter.py](backend/pc_client/database_adapter.py) defines the asynchronous
adapter contract. Its integration points are `start`, `close`,
`publish_current_sample`, `publish_missing_interval`, `upsert_history`,
`reconcile_provisional_intervals`, `publish_connection_state`, and
`publish_display_result`. The default adapter safely discards writes and reports
`persistence_configured=false`.

The database teammate can supply a synchronous no-argument factory returning an
object with that interface:

```powershell
$env:THERMOMETER_DATABASE_ADAPTER_FACTORY = "my_package.mysql_adapter:create_adapter"
.venv\Scripts\python main.py
```

Database credentials and driver-specific configuration belong in environment
or deployment secrets and must not be committed. History samples carry device,
boot ID, and sample sequence as the duplicate-safe identity. Batches also state
whether the ESP32 boot changed so the adapter can reconcile only appropriate
same-boot provisional intervals. Numeric values remain Celsius and all service
timestamps are timezone-aware UTC. The database average is calculated from both
valid sensor values in a snapshot regardless of display visibility.

For this integration, display commands intentionally use the direct localhost
REST path instead of Jira's proposed MySQL `control_commands` queue. Confirmed
display results are still offered to the database adapter. The production web
UI should read temperature/history through its database-backed APIs; the BLE
`current` endpoint is diagnostic rather than a replacement data source.

## Python GUI test tool

Python 3.10 or newer is recommended. On Windows, Bluetooth must be enabled and the terminal must be allowed to use Bluetooth.

```powershell
Set-Location backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r pc_client\requirements.txt
.venv\Scripts\python.exe -m pc_client.gui
```

In the GUI:

1. Select **Scan**.
2. Select the uniquely named thermometer.
3. Select **Pair & Connect**. The GUI asks for a masked six-digit passkey only when the device is not registered; Windows receives it without an operating-system prompt.
4. Use each sensor's button to control its logical display state and the ESP32 LED.

Existing authenticated bonds and registered credentials are reused. **Reset
Pairing** is permitted only while connected and application-authenticated. It
first asks the ESP32 to delete the owner bond, then removes the Windows bond and
the local CSV entry. Pairing is never deleted automatically at startup.

The GUI is deliberately retained as a hardware test tool. Its worker delegates
to the same `ThermometerBleService` used by the REST process, so pairing,
priorities, polling, history, and reconnect behavior do not have a second
implementation. The GUI keeps manual startup selection while the production
service enables automatic sole-device discovery.

## Python library

[thermometer_client.py](backend/pc_client/thermometer_client.py) is independent of Tk and can be used directly. It exposes primitive exchanges; lifecycle retry and complete history orchestration belong to `ThermometerBleService`:

```python
import asyncio

from pc_client.thermometer_client import ThermometerBleClient


async def main() -> None:
    devices = await ThermometerBleClient.discover()
    if not devices:
        raise RuntimeError("thermometer not found")

    client = ThermometerBleClient(devices[0].device, passkey="012345")
    try:
        await client.connect()
        current = await client.get_current()
        print(current)

        await client.set_display(sensor_id=1, enabled=True)
        history_meta = await client.get_history_meta()
        print(history_meta)
    finally:
        await client.close()


asyncio.run(main())
```

The direct low-level client does not read `paired_devices.csv`, so its caller
must supply the device credential. Public operations are `discover`, `pair`, `connect`, `disconnect`,
`forget_pairing`, `get_current`, `set_display`, `get_history_meta`,
and `get_history_chunk`. `connect` calls `pair` automatically unless its caller
has already ensured the bond;
the service coordinates `request_bond_reset` with `forget_pairing` for the
authenticated two-sided reset.

[ble_service.py](backend/pc_client/ble_service.py) is the higher-level reusable
controller. Its public operations are `start`, `stop`, `scan`, `connect`,
`reconnect`, `disconnect`, `pair`, `forget_pairing`, `get_status`, `get_current`,
`set_display`, `request_history_sync`, and `get_operation`. Applications that
need continuous polling, reconnect, operation tracking, or persistence should
use this class instead of coordinating `ThermometerBleClient` directly.

## Wire protocol

All multibyte fields are little-endian. Temperatures are signed `int16` centi-degrees Celsius. Boot IDs and sample sequences are `uint32`.

Every packet starts with this 8-byte header:

| Offset | Type | Field |
|---:|---|---|
| 0 | `uint8` | protocol version |
| 1 | `uint8` | opcode |
| 2 | `uint16` | request ID |
| 4 | `uint16` | payload length |
| 6 | `uint8` | status (`0` in requests) |
| 7 | `uint8` | flags (`bit 0` marks a response) |

The response echoes the opcode and request ID. Unsupported versions are rejected without changing state.

| Opcode | Name | Request payload | Successful response payload |
|---:|---|---|---|
| `0x01` | `GET_CURRENT` | none | boot ID, newest sequence, both sensor snapshots, average |
| `0x02` | `SET_DISPLAY` | sensor ID `u8`, enabled `u8` | sensor ID, resulting visible state, enabled flag |
| `0x03` | `GET_HISTORY_META` | none | boot ID, newest sequence, both counts and oldest sequences |
| `0x04` | `GET_HISTORY_CHUNK` | sensor ID `u8`, start sequence `u32`, count `u8` | sensor ID, start sequence, count, record size, complete records |
| `0x05` | `AUTH_BEGIN` | none | device identity (6 bytes), boot ID, fresh nonce (16 bytes) |
| `0x06` | `AUTH_PROVE` | HMAC-SHA-256 proof (32 bytes) | none |
| `0x07` | `RESET_BOND` | none | none |

A history record is sequence `u32`, temperature `i16`, and data status `u8`. The Python library sizes chunk requests from the negotiated ATT MTU, up to 32 records.

Visible states are `OFF=0`, `ON=1`, and `DISCONNECTED=2`. Data status is `VALID=0` or `DISCONNECTED=1`.

Response status values are:

- `0`: success
- `1`: invalid command
- `2`: invalid sensor
- `3`: invalid value
- `4`: not available
- `5`: internal error
- `6`: unsupported protocol version
- `7`: application authentication required
- `8`: authentication proof failed
- `9`: authentication temporarily locked

Both characteristics require encrypted, authenticated access. Pairing uses BLE
Secure Connections with MITM protection and bonding. Protocol version 2 adds a
second, requester-driven proof: `AUTH_BEGIN` creates a five-second, single-use
nonce, and `AUTH_PROVE` sends HMAC-SHA-256 over the configured domain, protocol
version, device identity, boot ID, and nonce. The raw passkey is never sent in
an application packet. Temperature, history, display, and reset commands are
rejected until both layers succeed. Three failed proofs cause the configured
temporary lockout, and authentication is cleared whenever the link disconnects.

The standard Bleak Windows backend only handles Confirm Only pairing. Before
opening a GATT session, this project resolves the selected device's Windows BLE
Association Endpoint and performs its Provide PIN ceremony directly. The
per-device six-digit passkey is supplied during enrollment and the refreshed bond
must report `EncryptionAndAuthentication`. GATT traffic then uses an unmodified
`BleakClient` with pairing disabled.

GATT service discovery is uncached during development. Windows bonds are kept
until the authenticated owner selects **Reset Pairing**, so normal application
restarts and automatic reconnects do not repeat the security ceremony. NimBLE
bond persistence remains enabled. Repeat pairing is rejected instead of
silently replacing an ESP32-side owner record.

## Tests

### Python unit tests

From a fresh checkout, create the backend environment and install the
development dependency set from the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\pc_client\requirements-dev.txt
backend\.venv\Scripts\python.exe master_test.py
```

The tests cover byte layout, request IDs, response validation, current/history
decoding, incomplete-record rejection, requester-only ordering, display control,
MTU-aware chunk sizing, controller state/reconnect behavior, provisional poll
slots, priority preemption, history budgets/retries, database isolation, GUI
delegation, ASGI lifespan, every REST contract, credential registry behavior,
challenge proof construction, autonomous state transitions, and API error
mapping. The suite uses mocked BLE and Windows pairing boundaries, so it does
not require an ESP32 or Bluetooth adapter. `master_test.py` returns zero only
when the entire discovered suite passes.

### Firmware build tests

The firmware validation presently consists of protocol-generation checks, a
clean ESP-IDF build, and hardware acceptance; there is no separate on-target
Unity test application yet. In an initialized ESP-IDF 6.x terminal:

```powershell
Set-Location firmware
if (-not (Test-Path device_config.cmake)) {
    Copy-Item device_config.cmake.example device_config.cmake
}
# Set a unique six-digit passkey if this is a new local configuration.
idf.py set-target esp32
idf.py fullclean
idf.py build
idf.py size
```

The clean build validates the shared JSON, creates
`firmware/build/generated/thermometer_config.h`, compiles the selected
sensor/display implementations, links the application, and checks its partition
size. Use `idf.py menuconfig` to compile-check all four independent fake/real
sensor and display combinations documented in
[the firmware README](firmware/README.md#firmware-tests).

For the hardware smoke test, flash and monitor the default fake-sensor/LED
build, then use the service or GUI to verify secure connection, one-second
current readings, history synchronization, both display controls, and automatic
reconnection after an ESP32 power cycle. Firmware build and hardware failures
are intentionally not hidden inside the Python unit-test runner.
