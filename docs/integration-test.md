# Cross-platform ESP32-to-web integration test

This procedure verifies the complete project data path without a dedicated
Bluetooth dongle:

```text
ESP32 DS18B20 sensors -> built-in host Bluetooth -> Python backend -> MySQL
    -> frontend Node reader -> React readouts and graph
```

Windows runs the Python backend natively so Bleak can use WinRT. Linux runs
the backend in Docker and connects it to host BlueZ over system D-Bus. MySQL
and the frontend run in Docker on both systems.

## 1. Prerequisites

Both platforms require an ESP32, its USB programming cable, Docker with the
Compose plugin, and ESP-IDF 6.x. The PC's built-in Bluetooth adapter must be
enabled. Do not run another BLE scanner against the adapter during the test.

Windows additionally requires:

- Windows 10 or 11 with Docker Desktop using Linux containers.
- Python 3.10 or newer on `PATH`.
- The Windows Bluetooth service running.

Linux additionally requires:

- Native Linux with Docker Engine.
- BlueZ 5.55 or newer, `bluetoothctl`, and `curl`.
- A powered controller visible in `bluetoothctl show`.
- `/run/dbus/system_bus_socket` from the host BlueZ service.

On the first launch, the platform backend script creates `backend/.env` from
`backend/.env.example`. This one gitignored file controls both platform paths.
Local ports 3306, 5173, and 8000 are published only on loopback.

## 2. Wire, build, and flash the production firmware

Connect sensor 1's DS18B20 data line to GPIO14 and sensor 2's data line to
GPIO27. Each probe must use three-wire power and its own approximately 4.7 kOhm
pull-up from data to 3.3 V; parasitic power is not supported. From `firmware/`,
copy `device_config.cmake.example` to the gitignored `device_config.cmake`, then
replace `000000` with a unique six-digit PIN. The default Kconfig selection is
the physical DS18B20 backend.

Windows example:

```powershell
Copy-Item device_config.cmake.example device_config.cmake
# Edit device_config.cmake before continuing.
idf.py set-target esp32
idf.py build
idf.py -p COM5 flash monitor
```

Linux example:

```bash
cp device_config.cmake.example device_config.cmake
# Edit device_config.cmake before continuing.
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

Use the board's actual serial port. Leave it powered and wait for it to
advertise as `Thermometer-XXXXXX`.
After updating the integration code, reflash the ESP32: the stable history
snapshot is a firmware change. Restarting only Python and the web app will
not fix `NOT_AVAILABLE` on an older image.

## 3. Start a fresh database and the backend

Each backend launcher deliberately removes the prior MySQL volume, recreates
the schema, and verifies that `temperature_samples` contains zero rows. The
separate `backend/.runtime/paired_devices.csv` enrollment registry survives.
For a code-update restart that retains existing samples, use
`backend/run.ps1 -KeepDatabase` on Windows or `backend/run.sh --keep-db` on
Linux after stopping the backend process. Without that option, the database
is intentionally reset.

To recover all thermometer pairings known to this project while retaining the
database, add `-ResetPairings` on Windows or `--reset-pairings` on Linux. This
does not remove unrelated Bluetooth devices. The next Connect asks for the
six-digit firmware PIN again.

### Windows

From a PowerShell terminal at the repository root:

```powershell
.\backend\run.ps1
```

The launcher starts only MySQL in Docker, prepares `backend/.venv`, and runs
`backend/main.py` on Windows. BLE therefore uses the built-in adapter through
WinRT. Keep this terminal open.

### Linux

From a terminal at the repository root:

```bash
bash backend/run.sh
```

The launcher starts MySQL and the `linux` Compose profile. The backend
container uses host BlueZ through `/run/dbus/system_bus_socket`; it is neither
privileged nor given direct HCI access. Keep this terminal open.

On either platform, <http://127.0.0.1:8000/healthz> must report `ready: true`,
`persistence_configured: true`, and `database_adapter_available: true`.
`/api/v1/ble/status` must report `winrt` on Windows or `bluez` on Linux.

## 4. Start the web application

Open a second terminal at the repository root.

Windows:

```powershell
.\frontend\run.ps1
```

Linux:

```bash
bash frontend/run.sh
```

Open <http://127.0.0.1:5173>. The UI must identify the Python BLE connector.
On Windows the browser calls the native loopback BLE API directly using its
exact CORS allowlist. On Linux, Vite proxies BLE calls to the backend
container. On both systems, `/api/samples` remains relative and is served by
the Node process in the frontend container, which reads MySQL over the private
Compose network.

## 5. Pair and connect

1. Enter the six-digit PIN configured in `device_config.cmake`.
2. Click **Scan** and select `Thermometer-XXXXXX`.
3. Click **Connect**.
4. Wait for `CONNECTED` and `ready: true`.
5. Enable both sensor displays.

With either probe unplugged, its display control must remain OFF, its LCD row
must show `DISCONNECTED`, and MySQL must store a `DISCONNECTED` status with no
temperature. Connecting a valid probe makes it available on the following
successful one-second acquisition cycle.

An empty scan means the board is not advertising, Bluetooth is disabled, or
another process owns the scan. It is not a database or frontend error.

## 6. Verify every boundary

Inspect the newest database rows from either platform shell:

```text
docker compose --project-name ece4880-integration --env-file backend/.env --file backend/compose.yaml exec -T mysql sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SELECT id,boot_id,sample_seq,observed_at_utc,sensor1_c,sensor1_status,sensor2_c,sensor2_status,record_source FROM temperature_samples ORDER BY id DESC LIMIT 10"'
```

Then check these browser-facing endpoints:

```text
http://127.0.0.1:5173/api/samples/latest
http://127.0.0.1:5173/api/samples?seconds=320
http://127.0.0.1:8000/api/v1/ble/status
```

Acceptance criteria:

- MySQL gains rows approximately once per second with increasing
  `boot_id`/`sample_seq` identity and `LIVE` source.
- `/api/samples/latest` matches the newest MySQL row.
- Both web readouts and graph series update from those database rows.
- With both probes attached, both statuses are `VALID` and the database and UI
  show the same physical temperatures. Warming one probe changes only its
  corresponding series.
- Unplugging either probe produces graph gaps and `DISCONNECTED` status rather
  than a zero or repeated stale temperature; its display command is rejected
  until a valid DS18B20 is detected again.
- After a BLE reconnection, the backend automatically fetches the ESP32 history
  buffer and writes its original timestamps to MySQL. The graph replaces
  recoverable provisional gaps from the refreshed database window without a
  browser-issued BLE history request. Incomplete automatic retrieval is
  retried while connected. The ESP32's finite history buffer limits recovery
  after a sufficiently long outage.
- For the 300-second/10-second requirement, leave the ESP32 powered for at
  least five minutes before connecting. Start a timer when status first becomes
  `CONNECTED`. Within 10 seconds, `/api/v1/ble/status` must report
  `history_sync.state: "COMPLETE"`, `retrieved_counts: [300, 300]`,
  `sample_count: 300`, `persisted: true`, and `elapsed_seconds <= 10`.
  The Device connection panel shows the same result. The chart reads those
  MySQL rows every second and retains a 20-second viewing margin so the oldest
  pre-connection readings remain available by scrolling left when synchronization
  completes.
  If the panel says `INCOMPLETE`, check `failure_reason` and the ESP32's MTU
  log before investigating the graph.
  This firmware revision adds a compact 72-record history response and requests
  a 50 ms BLE connection interval. The Python backend falls back to the older
  32-record response when the ESP32 does not support the compact command, but
  the frozen-history and transfer-speed fixes require reflashing the ESP32.
  The ~5-second recovery target is an optimization goal, not yet a measured
  hardware result; verify both the negotiated ATT MTU and actual connection
  interval in the ESP32 serial log. A host may decline the preferred interval.
  On Linux, BlueZ 5.62+ exposes the negotiated characteristic MTU to Bleak.
  Older BlueZ versions may report only 23 bytes, making the 10-second transfer
  target unattainable even though the rest of the integration still runs.

## 7. Verify reset and enrollment persistence

Stop the frontend, then stop and rerun the platform's backend launcher. It
must verify a zero-row database before starting the poller, while
`backend/.runtime/paired_devices.csv` remains available after successful
enrollment. Windows bonds remain owned by WinRT; Linux bonds remain owned by
host BlueZ. Do not commit `backend/.env`, `.runtime/`, `.venv/`, or the local
firmware device configuration.

## Automated checks

The base Compose configuration contains only `mysql` and `frontend`; the
`backend` service appears only with `--profile linux`.

```powershell
docker compose --env-file backend/.env.example --file backend/compose.yaml config --services
docker compose --profile linux --env-file backend/.env.example --file backend/compose.yaml config --services
python master_test.py
Set-Location frontend
npm test
npm run lint
npm run build
```
