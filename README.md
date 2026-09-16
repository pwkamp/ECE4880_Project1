# Networked Thermometer

ESP32 firmware, Python BLE connector, MySQL schema, and the computer console.

## Computer console

The web app lives in [`frontend/`](frontend/). The **computer** component of
the ECE:4880 dual-sensor networked thermometer system.

> The console defaults to **mock data**. Point it at the Python BLE
> connector with `VITE_DATA_SOURCE=ble` (see
> [Connecting the console to BLE and MySQL](#connecting-the-console-to-ble-and-mysql)).

---

## Screenshots

![Computer console with both sensor readouts and the 300-second chart recorder](docs/screenshots/console.png)

*Main console: large real-time readouts for both sensors, the fixed-scale
chart recorder (the hatched band is a simulated data outage), sensor display
toggles, and the threshold-alert configuration.*

<!-- Add more screenshots here as you capture them, e.g.:
![Off-scale spike](docs/screenshots/offscale.png)
![Simulated alert](docs/screenshots/alert.png)
-->

---

## Running it

**Prerequisites:** Node.js 20+ and npm (developed on Node 24). One-shot
install (creates `.env` files and a Python venv when Python is present):

```bash
bash scripts/setup.sh
cd frontend
npm run dev
```

`scripts/setup.sh` is not Docker: the ESP32 talks over the **host** Bluetooth
adapter (WinRT / BlueZ), which containers do not own cleanly.

If you already have dependencies:

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints — default <http://localhost:5173>. The chart is
pre-seeded with 300 s of history, so it's full immediately. Hot-reloads on
save; `Ctrl+C` stops it.

| Command | Purpose |
| --- | --- |
| `cd frontend && npm run dev` | Run the console in development |
| `cd frontend && npm test` | Unit tests: alert logic, readout logic, mock data source, an App render smoke test |
| `cd frontend && npm run build` | Type-check + production build into `frontend/dist/` |
| `cd frontend && npm run preview` | Serve the production build locally |
| `cd frontend && npm run lint` | oxlint |

No cloud services, API keys, or internet access are required for the default
console (mock data + logged SMS).

The web console lives in [`frontend/`](frontend/). `cd frontend && npm run dev` is how you run it. BLE and MySQL
are optional extra processes you start **in addition** to that, not instead of
it.

## Connecting the console to BLE and MySQL

This is the full wiring guide. The React app on `:5173` stays; you add the
Python BLE connector on `:8000` and (optionally) MySQL so live temperatures
come from the third box instead of the in-browser mock.

### What talks to what

There are **three processes** on one PC, plus an ESP32 on Bluetooth, plus a
MySQL database. The browser never opens a BLE socket and never talks to MySQL
directly.

```
  ESP32 thermometer  --BLE-->  Python FastAPI  --writes-->  MySQL
  (firmware, fake or           backend/main.py              thermometer.
   real sensors)               127.0.0.1:8000               temperature_samples
                                      ^
                                      | HTTP /api/v1/ble/*
                                      |
  Browser  --same origin-->  Vite (:5173)  --proxy /api/v1-->  Python :8000
           React console                  --proxy /api----->  Node :8787
                                                            (SMS + MySQL reader)
                                      ^
                                      | GET /api/samples
                                      |
                                   MySQL (read path)
```

| Process | Command | Bind | Role |
| --- | --- | --- | --- |
| Web console | `cd frontend && npm run dev` (Vite half) | `http://localhost:5173` | UI: readouts, chart, scan/connect panel, alerts |
| Alert + sample reader | started with `npm run dev` in `frontend/` | `127.0.0.1:8787` | SMS delivery; **reads** `temperature_samples` when `MYSQL_URL` is set |
| BLE connector | `backend/.venv/bin/python main.py` | `127.0.0.1:8000` | Scan, pair, connect, poll the box at 1 Hz, **write** samples through a DB adapter |
| MySQL | `mysqld` / local MySQL | `127.0.0.1:3306` | Stores 1 Hz rows the console charts from |
| ESP32 | flashed firmware | BLE advertisement `Thermometer-XXXXXX` | Source of temperatures (fake-sensor firmware is fine for demo) |

FastAPI has **no CORS**. That is why the browser must go through Vite’s proxy
and not `fetch('http://127.0.0.1:8000/...')`. OpenAPI is still at
<http://127.0.0.1:8000/docs> in a normal browser tab for humans.

Interactive schemas (the ones the teammate meant):

| Method | Path | Used for |
| --- | --- | --- |
| `GET` | `/healthz` | Is the Python process up? |
| `GET` | `/api/v1/ble/status` | Phase (`DISCOVERING`, `CONNECTED`, …), `ready`, target MAC, errors |
| `POST` | `/api/v1/ble/scan` | Manual scan; returns `{ devices: [{ name, address, rssi }] }` |
| `POST` | `/api/v1/ble/connect` | Body `{ "address": "AA:BB:…", "passkey": "123456" }` (passkey optional until the service returns 401) |
| `POST` | `/api/v1/ble/reconnect` | Resume retries after a disconnect |
| `POST` | `/api/v1/ble/disconnect` | Drop the GATT link; does not forget the last target |
| `POST` | `/api/v1/ble/pair` | Explicit pair/enroll |
| `DELETE` | `/api/v1/ble/pairing/{address}` | Forget a bond |
| `GET` | `/api/v1/ble/current` | Live snapshot (fallback if MySQL is empty / unconfigured) |
| `PUT` | `/api/v1/ble/displays/{sensor_id}` | Body `{ "enabled": true }`. Sensor id is `1` or `2`. This is the virtual display button. |
| `POST` | `/api/v1/ble/history/sync` | Pull the 300-sample ring off the box into the DB adapter |
| `GET` | `/api/v1/operations/{operation_id}` | Poll a 202 connect/pair/sync |

The console’s **Device connection** panel drives scan / connect / disconnect /
reconnect. Sensor display checkboxes call `PUT /displays/{id}`. Chart and
readouts prefer MySQL; they use `/current` only when the Node reader is off.

### End-to-end data path (this is the important part)

1. Firmware samples both probes once per second (fake waveforms or real ADCs).
2. Python, once `ready=true`, polls `GET`-equivalent GATT current and asks the
   **database adapter** to persist a row (`publish_current_sample`).
3. A real adapter (owned by the DB teammate, **not in this repo**) `INSERT`s
   into `thermometer.temperature_samples`.
4. The Node service on `:8787` **SELECTs** those rows (`GET /api/samples` and
   `/api/samples/latest`) when `MYSQL_URL` is set.
5. `PythonBleSource` in the React app turns each row into a `ThermometerFrame`
   (celsius, connected, display-enabled) for the chart and big numbers.

If step 3 is still the built-in **no-op adapter**, MySQL stays empty. The
console then falls back to step 2’s live snapshot (`/api/v1/ble/current`) so
you can still demo with only Python + an ESP32.

### Prerequisites

- **Node.js 20+** and npm — web console.
- **Python 3.10+** — BLE connector. 3.12/3.14 are fine.
- **An ESP32** flashed with this repo’s `firmware/` (fake sensors are the
  default and are enough). The box must be powered and advertising.
- **Bluetooth adapter** on the PC. The Python connector **detects the OS at
  startup** (`pc_client/platform_runtime.py` via `sys.platform`) and picks the
  pairing stack — you do not choose Windows vs Linux in config.
  - **Windows 10/11:** WinRT PIN pairing (`pc_client/windows_pairing.py`).
    Auto-discover stays on (original design).
  - **Linux:** BlueZ pairing via D-Bus (`pc_client/linux_pairing.py`). The
    connector **does not auto-scan in a loop** (that was locking up laptops).
    Use the console **Scan** then **Connect**, and type the six-digit firmware
    PIN. Your user should be in the `bluetooth` group.
  - **macOS:** still pair in OS Settings, then Connect (no native PIN helper).
- **MySQL 8** if you want the chart seeded from the database (optional for a
  first BLE bring-up).
- **One Python connector at a time.** It owns the BLE adapter. A second copy
  can lock up Bluetooth. On Linux, leave auto-scan off unless you set
  `THERMOMETER_LINUX_AUTO_SCAN=1` (not recommended).

Firmware passkey: copy
`firmware/device_config.cmake.example` → gitignored
`firmware/device_config.cmake` and set a unique six-digit PIN. The advertised
name is `Thermometer-` plus the MAC suffix. That same PIN is what you type in
the console’s **Pairing passkey** field (or Windows’ pairing dialog).

### 1. Start MySQL and create the schema (optional, but this is the “temps from DB” path)

Install MySQL locally. Then from the repo:

```bash
mysql -u root -p < backend/database/schema.sql
```

That script **drops and recreates** the `thermometer` database. Do not point it
at a database you care about. The table is `temperature_samples` (one row per
1 Hz sample, both probes as columns):

| Column | Meaning |
| --- | --- |
| `observed_at_utc` | PC-clock UTC time the connector stamped |
| `sensor1_c` / `sensor2_c` | Celsius `DECIMAL(5,2)`, or `NULL` if not trustworthy |
| `sensor1_status` / `sensor2_status` | `VALID`, `DISCONNECTED`, `NOT_RETRIEVED`, `MISSING` |
| `average_c` / `average_valid` | Average only when both probes are valid |
| `record_source` | `LIVE`, `HISTORY`, or `PROVISIONAL` |
| `boot_id` / `sample_seq` | Firmware sequence; `NULL` on provisional gap rows |

Create a MySQL user the Node reader (and, separately, the Python writer
adapter) can use, for example:

```sql
CREATE USER 'thermo'@'127.0.0.1' IDENTIFIED BY 'pick-a-password';
GRANT SELECT, INSERT, UPDATE ON thermometer.* TO 'thermo'@'127.0.0.1';
FLUSH PRIVILEGES;
```

The **reader** URL goes in `frontend/server/.env` (the Node service):

```
MYSQL_URL=mysql://thermo:pick-a-password@127.0.0.1:3306/thermometer
```

Copy `frontend/server/.env.example` → `frontend/server/.env` if you do not have one yet.
`frontend/server/.env` is gitignored.

The **writer** is not this Node URL. Before `python main.py`, set the
in-repo adapter from the merged database PRs:

```
THERMOMETER_DATABASE_ADAPTER_FACTORY=pc_client.mysql_adapter:create_adapter
THERMOMETER_DB_HOST=127.0.0.1
THERMOMETER_DB_PORT=3306
THERMOMETER_DB_USER=thermo
THERMOMETER_DB_PASSWORD=pick-a-password
THERMOMETER_DB_NAME=thermometer
```

That adapter implements `ThermometerDatabaseAdapter` in
`backend/pc_client/mysql_adapter.py`. If the factory is unset, Python uses
`NoOpDatabaseAdapter` and stores nothing; `GET /healthz` then shows
`"persistence_configured": false` and the console falls back to
`/api/v1/ble/current`. Schema details (including `users` / alert tables and
`failure_reason`) are in `backend/database/README.md`.

Confirm the reader without the UI:

```bash
# after `cd frontend && npm run dev` is up, or curl the Node port directly
curl -sS http://127.0.0.1:8787/api/samples/latest
# { "configured": false, "row": null }     → MYSQL_URL unset
# { "configured": true, "row": { ... } }   → reader on; row may still be null if empty
```

### 2. Start the Python BLE connector

From `backend/` (so `pc_client` and the sibling `protocol/` directory resolve):

```bash
cd backend
python3 -m venv .venv
# Windows:  python -m venv .venv
#           .venv\Scripts\pip.exe install -r pc_client\requirements.txt
#           .venv\Scripts\python.exe main.py
.venv/bin/pip install -r pc_client/requirements.txt
.venv/bin/python main.py
```

You should see Uvicorn on `http://127.0.0.1:8000`. Leave this terminal open.

- OpenAPI UI: <http://127.0.0.1:8000/docs>
- Raw schema: <http://127.0.0.1:8000/openapi.json>
- Health: `curl -sS http://127.0.0.1:8000/healthz`

The same `main.py` **detects the OS** (`sys.platform`) and chooses pairing:

| `GET /api/v1/ble/status` field | Windows | Linux |
| --- | --- | --- |
| `host_os` | `windows` | `linux` |
| `pairing_backend` | `winrt` | `bluez` |
| `auto_discover_on_start` | `true` | `false` |
| Idle `phase` | `DISCOVERING` (background scan) | `DISCONNECTED` (wait for **Scan**) |

`DISCONNECTED` on Linux is idle, not a failure. Confirm detection with:

```bash
curl -sS http://127.0.0.1:8000/api/v1/ble/status
```

Successful enrollment writes gitignored `backend/paired_devices.csv` (plaintext
per-device credentials). Do not commit it.

Optional Tk hardware tool (not the web UI):

```bash
.venv/bin/python -m pc_client.gui
```

### 3. Point the web console at BLE (the web app is still required)

The console **defaults to mock data** so `cd frontend && npm run dev` alone still works for UI
work. To use the Python service, create **`frontend/.env`** (gitignored;
Vite only reads it at startup):

```
VITE_DATA_SOURCE=ble
```

There is a template in [`frontend/.env.example`](frontend/.env.example). Then:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. You should see:

- Subtitle **Computer console — Python BLE connector** (not “mock data source”)
- A **Device connection** panel (scan, passkey, connect, disconnect, reconnect)
- **Demo controls (mock only) gone** — those only exist on the simulator

Vite proxies (see `vite.config.ts`):

| Browser URL | Proxied to | Service |
| --- | --- | --- |
| `/api/v1/*` | `http://127.0.0.1:8000/api/v1/*` | Python BLE |
| `/api/*` (everything else, e.g. `/api/notify`, `/api/samples`) | `http://127.0.0.1:8787/api/*` | Node SMS + MySQL reader |

If you change `frontend/.env`, restart Vite. `VITE_*` values are baked in at dev-server
start.

### 4. Prepare the PC Bluetooth stack (do this before Scan)

The browser does not talk to Bluetooth. Only `backend/main.py` does. Prepare
the **same machine** that will run Python.

#### Firmware (the ESP32)

1. Flash this repo’s `firmware/` (fake sensors are enough).
2. Copy `firmware/device_config.cmake.example` → gitignored
   `firmware/device_config.cmake` and set a **unique six-digit PIN** (ASCII
   digits only, e.g. `482913`).
3. The advertised name is `Thermometer-` plus a MAC suffix
   (`Thermometer-A1B2C3`). Scan will not list a device named something else.
4. Power the box and wait several seconds so it is advertising **before** you
   click Scan. If it is off, Scan returns `{ "devices": [] }` — that is a
   radio result, not a crashed connector.

That same PIN is what you type in the console **Pairing passkey** field.

#### Linux (BlueZ)

Continuous discovery every ~2 s can wedge BlueZ on laptops, so production
Linux **does not auto-scan**. You click **Scan** once per attempt.

1. Install BlueZ if needed (`bluez`, and a working system D-Bus).
2. Put your login in the `bluetooth` group, then **log out and back in**
   (a new terminal is not enough until the session is restarted):

   ```bash
   sudo usermod -aG bluetooth "$USER"
   groups   # must list bluetooth after re-login
   ```

3. Power the adapter and allow pairing:

   ```bash
   bluetoothctl show
   ```

   You want `Powered: yes`. If `Pairable: no`:

   ```bash
   bluetoothctl power on
   bluetoothctl pairable on
   ```

4. Do **not** leave `bluetoothctl scan on` running in another terminal while
   `main.py` is using the adapter. One owner at a time.
5. Do **not** set `THERMOMETER_LINUX_AUTO_SCAN=1` unless you are debugging
   Windows-style probing on a machine that can survive it.
6. Pairing uses a BlueZ D-Bus Agent1 (`pc_client/linux_pairing.py` +
   `dbus-fast`, pulled in with Bleak). You should not need to type the PIN
   in `bluetoothctl` if Connect from the console succeeds.

If Scan or pair fails with a D-Bus / permission error, you are usually not
in `bluetooth`, or another process owns `hci0`.

#### Windows 10/11 (WinRT)

1. Turn **Bluetooth** on in Settings.
2. You do **not** need to pair the ESP32 in Windows Settings first. The
   connector pairs with WinRT (`pc_client/windows_pairing.py`) using the
   six-digit PIN you send on Connect.
3. Auto-discover stays **on**. With one known device it will try to
   pair/connect by itself. With zero devices, `phase` stays `DISCOVERING`
   until the box advertises. You can still click **Scan** and **Connect**.
4. If Windows already bonded the box with the wrong PIN, forget it in
   Settings → Bluetooth (or `DELETE /api/v1/ble/pairing/{address}`) and
   Connect again from the console.

#### macOS

There is no PIN helper in this repo. Pair in macOS Bluetooth settings with
the firmware PIN, then Scan/Connect in the console.

### 5. Connect a thermometer from the UI

Order matters. Python must already be on `:8000`, Vite must have been
started from `frontend/` with `VITE_DATA_SOURCE=ble`, and the ESP32 must be advertising.

1. Open <http://localhost:5173>. Subtitle should read **Python BLE connector**.
   The **Device connection** panel should name the detected OS (Linux/BlueZ
   or Windows/WinRT).
2. Power the ESP32; wait until it advertises.
3. Type the six-digit firmware PIN in **Pairing passkey**.
4. Click **Scan** (a few seconds). You want a row `Thermometer-XXXXXX` and a
   MAC. Empty list = nothing with that name on the air (box off, wrong
   firmware, Bluetooth off, or another tool already connected).
5. Click **Connect** on that row. Status should move
   `PAIRING` → `CONNECTING` / `VERIFYING` → **Connected**.
6. Use **Sensor display** checkboxes as the virtual buttons
   (`PUT /displays/1` and `/displays/2`).
7. Readouts and the 300 s chart should move. If MySQL is wired they come from
   `temperature_samples`; otherwise from `/api/v1/ble/current`.

Status meanings:

| UI / `phase` | Meaning |
| --- | --- |
| `DISCONNECTED` | Idle (normal on Linux until Scan/Connect) |
| `DISCOVERING` | Background or manual scan in progress |
| `SELECTION_REQUIRED` | Several unknown devices; pick one |
| `AUTHENTICATION_REQUIRED` | Six-digit PIN missing or rejected |
| `PAIRING` | OS bond (WinRT or BlueZ) |
| `CONNECTING` / `VERIFYING` | GATT + protocol auth |
| `CONNECTED` | Link up; `ready` means first snapshot succeeded |
| `RECONNECTING` | Radio dropped; it will retry |

After a successful first enroll, `backend/paired_devices.csv` remembers the
PIN. Later power-cycles on **Windows** can reconnect without typing it again.
On **Linux**, click **Scan** then **Connect** if it does not resume (auto-scan
is off). **Disconnect** drops GATT but keeps the last target; forget the OS
bond with `DELETE /api/v1/ble/pairing/{address}` if you need a clean pair.

Connect from curl if you are debugging the API without the UI:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/ble/scan
curl -sS -X POST http://127.0.0.1:8000/api/v1/ble/connect \
  -H 'Content-Type: application/json' \
  -d '{"address":"AA:BB:CC:DD:EE:FF","passkey":"123456"}'
curl -sS http://127.0.0.1:8000/api/v1/ble/status
curl -sS http://127.0.0.1:8000/api/v1/ble/current
```

Replace the address and passkey. Connect returns **202** with an
`operation_id`; poll `/api/v1/operations/{id}` until `state` is terminal.

### 6. Checklist: “is it actually connected?”

| Check | Healthy result |
| --- | --- |
| `curl :8000/healthz` | `"ready": true` (process up; `controller_state` may still be `DISCOVERING`) |
| `curl :8000/api/v1/ble/status` | `"connected": true`, `"ready": true`, `target.address` set |
| `curl :8000/api/v1/ble/current` | `"available": true`, `snapshot.sensors[].temperature_c` numbers or nulls |
| `curl :8787/api/samples/latest` | `"configured": true` and a row, **or** `"configured": false` and the UI using `/current` |
| Browser subtitle | “Python BLE connector” |
| Chart | New points on the right at ~1 Hz after `ready` |

### Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Subtitle still says mock; no Device panel | `frontend/.env` missing `VITE_DATA_SOURCE=ble`, or Vite not restarted |
| Device panel: scan fails / proxy errors | Python not running on `:8000`, or a second process stole the port |
| Phase stuck on `DISCOVERING` (Windows) or `DISCONNECTED` after Scan (Linux) | ESP32 off, out of range, wrong firmware name prefix (`Thermometer-`), or PC Bluetooth disabled |
| Scan returns `{ "devices": [] }` | Box not advertising. Linux Bluetooth permissions (`bluetooth` group) can also hide devices |
| Linux: D-Bus / “not in group bluetooth” | `sudo usermod -aG bluetooth $USER`, then log out and back in |
| Linux: adapter `Pairable: no` | `bluetoothctl pairable on` |
| `401` on connect | Passkey missing/wrong; must match `firmware/device_config.cmake` |
| `409` | Connector is busy (already connected / conflicting scan) |
| Chart empty but status `ready` | Displays off, both probes disconnected, or `/current` has nulls |
| Chart empty, `persistence_configured: false`, and `/current` also empty | No BLE snapshot yet — not a MySQL problem |
| `MYSQL_URL` set but `/api/samples/latest` is 503 | Wrong password, MySQL down, or schema not applied |
| Samples configured but row always null | Writer adapter still no-op, or history never synced |
| Machine/Bluetooth hard-locks | Two `main.py` processes. On Linux do **not** set `THERMOMETER_LINUX_AUTO_SCAN=1`. Stop with `Ctrl+C`. |
| Browser CORS errors to `:8000` | You called Python from the page without the Vite proxy. Use relative `/api/v1/...` |

### Switching back to mock data

Remove `VITE_DATA_SOURCE=ble` from `frontend/.env` (or set it to anything other than
`ble`) and restart `npm run dev` from `frontend/`. You do not need Python or MySQL. Demo
controls come back. This is the default for UI work.

## Running with SMS alerts

`cd frontend && npm run dev` starts the web app **and** a small delivery service
(`frontend/server/`, on `127.0.0.1:8787`). The browser evaluates alerts against the
mock sensor data as usual and POSTs each HIGH/LOW transition to the service.

Delivery mode is set by `frontend/server/.env` (copy from `frontend/server/.env.example`):

| `SMS_MODE` | Behaviour | Needs |
| --- | --- | --- |
| `console` (default) | Logs the message to the server console. Nothing is sent. | nothing |
| `test` | Calls the Twilio API with **test credentials** and [magic numbers](https://www.twilio.com/docs/iam/test-credentials). Exercises the real request path without sending or charging. | Twilio test SID/token; `TWILIO_FROM_NUMBER=+15005550006` |
| `live` | Sends a real SMS. | Twilio live SID/token, an SMS-capable Twilio number, and (on a trial account) a verified destination number |

Set the destination phone number in the app's **Threshold alerts** panel
(E.164 format, e.g. `+15551234567`). The default destination is already a
valid dummy E.164 number. To test end to end in `console` mode:
open the app, use the **Demo controls** to pin a sensor above 50 °C, and
watch the **api** terminal for a line like
`Text message sent to +15555550123: "Temperature high: …"` and the app's Alert
activity panel for the delivery badge.

If `ALERT_API_TOKEN` is set in `frontend/server/.env`, also set
`VITE_ALERT_API_TOKEN` (same value) in `frontend/.env` so the console
can authenticate.

---

## What it does (mapped to the lab spec)

**Real-time display**
- Both sensors, independently, large font, updates once per second.
- °C / °F toggle in the header (affects readouts *and* the chart, live, without
  resetting history).
- `unplugged sensor` message when a sensor is disconnected.
- `no data available` for both sensors when the third box's switch is off.
- Live numbers resume automatically the moment data returns — no refresh.

**Virtual sensor control**
- A toggle per sensor turns its display on/off from the computer — the software
  equivalent of the physical button on the box. Takes effect in well under 1 s.

**Chart recorder (last 300 s)**
- New point on the right, scrolls right-to-left, oldest falls off the left.
- Y-axis is **fixed** at 10–50 °C (50–122 °F) and never auto-scales.
- X-axis is labelled "seconds ago from current time", 300 → 0.
- History seeds on startup (well within the spec's 10 s).

**Missing vs. off-scale data** — deliberately distinct:
- **Missing** (switch off / unplugged / display off): a hatched band in the
  sensor's colour, labelled "no data". The chart keeps scrolling through it.
- **Off-scale** (a real reading above 50 °C or below 10 °C): a solid triangle
  clipped to the top or bottom rail. The numeric readout still shows the true
  value with an "off chart scale" note.

**Threshold alerts**
- Configure max threshold, min threshold, an independent custom message for
  each, and an E.164 destination phone number.
- Crossing a threshold logs a `SIMULATED ALERT` entry and POSTs the event to
  the local delivery service (see
  [Running with SMS alerts](#running-with-sms-alerts)). In the default
  `console` mode the service logs the SMS and does not send anything.
- Fires **once per crossing**, not every second. Re-arms only after the reading
  returns inside the band.

**Demo controls** (bottom panel, mock data only)
- Flip the third-box power switch on/off.
- Unplug / re-plug each sensor.
- Spike a sensor to 60 °C or drop it to 0 °C (off-scale), then resume.
- Reset everything.

These are how you demonstrate spec compliance without hardware. They disappear
automatically once a real data source is connected.

---

## Architecture: the data-source seam

Everything the UI knows about the hardware goes through **one interface**,
`ThermometerSource`, defined in
[`src/datasource/types.ts`](src/datasource/types.ts). The UI, hooks, and
business logic depend only on that interface — never on the mock.

```
                    ┌───────────────────────────────┐
   React UI  ─────▶  │  ThermometerSource (interface) │
   hooks / lib       └───────────────┬───────────────┘
                                     │  one of:
                     ┌───────────────┴────────────────┐
                     ▼                                ▼
        MockThermometerSource            PythonBleSource
        (default simulator)              (VITE_DATA_SOURCE=ble)
                                         FastAPI :8000 + MySQL reader
```

The active source is chosen in [`src/datasource/index.ts`](src/datasource/index.ts)
(`VITE_DATA_SOURCE=ble` vs mock). See
[Connecting the console to BLE and MySQL](#connecting-the-console-to-ble-and-mysql).

```
src/
  datasource/
    types.ts                  the hardware contract — READ THIS FIRST
    mockThermometerSource.ts   the simulator
    pythonBleSource.ts         FastAPI BLE + MySQL sample reader
    bleClient.ts / bleMap.ts   HTTP client and frame mapping
    index.ts                   exports the active source (the swap point)
  hooks/useThermometer.ts      subscribes, keeps the rolling 300 s window
  lib/
    temperature.ts             C/F conversion, the fixed 10–50 scale
    readout.ts                 what the big number shows
    alerts.ts                  pure threshold evaluation, once-per-crossing
  components/                  RealtimeReadout, ChartRecorder, SensorControls,
                               AlertSettings, AlertLog, DebugPanel
  App.tsx
```

### The data contract

At roughly 1 Hz the source produces a `ThermometerFrame`:

```ts
interface ThermometerFrame {
  timestamp: number;                 // epoch milliseconds
  switchState: 'on' | 'off';         // third-box power switch
  readings: Record<1 | 2, {
    sensorId: 1 | 2;
    celsius: number | null;          // null when there is NO reading
    connected: boolean;              // sensor physically plugged in
    enabled: boolean;                // sensor display on (button state)
  }>;
}
```

`celsius` must be `null` — not `0`, not a stale value — whenever the box cannot
produce a fresh reading: switch off, sensor unplugged, or sensor display turned
off. Send raw Celsius; the app handles unit conversion and clamping.

Interface methods:

| Method | Purpose |
| --- | --- |
| `getFrame()` | latest frame, for first render |
| `getSwitchState()` | convenience accessor |
| `setSensorEnabled(id, bool)` | the virtual button; must appear in the stream within 1 s |
| `subscribe(fn)` | ~1 Hz stream of frames; returns an unsubscribe function |
| `getHistory(seconds)` | backlog to seed the chart on startup (may return `[]`) |
| `start()` / `stop()` | begin / end the stream |

---

## Connecting to the real hardware

This is the plan for wiring the console to the actual third box, the sensor
probes, and the phone. **None of it changes the UI** — it is all one new file
plus firmware work.

### 1. Physical piece → what it maps to

| Real thing | Interface element | What has to be built |
| --- | --- | --- |
| Third-box microcontroller | the transport (below) | firmware that emits a JSON frame ~1 Hz |
| Power switch | `frame.switchState` | firmware reports `'off'`, **or** the console infers "off" from loss of signal (see step 4) |
| Sensor probe 1 / 2 | `readings[n].celsius` | ADC / 1-Wire read, converted to °C, sent raw |
| Probe unplugged | `readings[n].connected = false`, `celsius = null` | firmware detects an open circuit / out-of-range read on that channel |
| Physical display button | `readings[n].enabled` | firmware toggles a per-sensor flag and reports it |
| Console's on/off toggle | `setSensorEnabled(id, bool)` | firmware accepts a command message and applies it to the same flag |
| The phone | the alert log → real SMS/email | a small backend + a provider account (see below) |

### 2. Choose a transport (box ↔ computer)

Pick based on what the box's microcontroller can do:

| Transport | Good when | `RealThermometerSource` uses |
| --- | --- | --- |
| **WebSocket** (box runs a WS server, e.g. on an ESP32) | box has Wi-Fi; want true 1 Hz push and a return channel for the virtual button | `new WebSocket('ws://<box-ip>:81')` |
| **HTTP polling** | simplest firmware; box exposes `GET /reading` and `POST /command` | `fetch` on a 1 s interval |
| **MQTT over WebSocket** | box is battery-powered / behind NAT; a broker sits in between | an MQTT-WS client, subscribe to `box/frame`, publish to `box/command` |
| **USB serial** (box plugged into the computer) | no networking on the box | the Web Serial API (`navigator.serial`, Chrome only), or a tiny local bridge that re-exposes serial as a WebSocket |

WebSocket is the recommended target: it matches the 1 Hz streaming model and
gives a built-in path for `setSensorEnabled` commands.

### 3. Define the on-the-wire JSON

Have the firmware emit exactly the `ThermometerFrame` shape so the adapter is
nearly a pass-through:

```json
{
  "timestamp": 1717000000000,
  "switchState": "on",
  "readings": {
    "1": { "sensorId": 1, "celsius": 22.4, "connected": true,  "enabled": true },
    "2": { "sensorId": 2, "celsius": null, "connected": false, "enabled": true }
  }
}
```

If the box's native format differs, the translation lives in one place — the
adapter's message handler — and nothing else needs to know.

### 4. Implement `RealThermometerSource`

One new file, `src/datasource/realThermometerSource.ts`, implementing
`ThermometerSource`. Skeleton:

```ts
import type { ThermometerFrame, ThermometerSource, SensorId } from './types';

export class RealThermometerSource implements ThermometerSource {
  private ws: WebSocket | null = null;
  private last: ThermometerFrame = OFFLINE_FRAME;          // switchState: 'off'
  private history: ThermometerFrame[] = [];
  private listeners = new Set<(f: ThermometerFrame) => void>();
  private staleTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private url: string) {}

  start() {
    this.ws = new WebSocket(this.url);
    this.ws.onmessage = (e) => {
      const frame = JSON.parse(e.data) as ThermometerFrame; // validate here
      this.ingest(frame);
    };
    this.ws.onclose = () => {
      this.scheduleReconnect();       // exponential backoff
      this.markOffline();             // synthesize switchState:'off' frames
    };
  }

  stop() { this.ws?.close(); this.ws = null; }

  private ingest(frame: ThermometerFrame) {
    this.last = frame;
    this.history.push(frame);
    this.trimHistory(frame.timestamp);           // keep ~360 s
    this.resetStaleWatchdog();                    // 3 s → markOffline()
    for (const l of this.listeners) l(frame);
  }

  getFrame() { return this.last; }
  getSwitchState() { return this.last.switchState; }
  getHistory(seconds: number) {
    const cutoff = Date.now() - seconds * 1000;
    return this.history.filter((f) => f.timestamp >= cutoff);
  }
  subscribe(fn: (f: ThermometerFrame) => void) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
  setSensorEnabled(sensorId: SensorId, enabled: boolean) {
    this.ws?.send(JSON.stringify({ type: 'setEnabled', sensorId, enabled }));
    // Optionally update this.last optimistically so the UI reacts < 1 s.
  }
}
```

Then change the one line in `src/datasource/index.ts`:

```ts
export const thermometerSource: ThermometerSource =
  new RealThermometerSource('ws://third-box.local:81');
```

Nothing in `src/components`, `src/hooks`, or `src/lib` changes. The demo-control
panel hides itself because `RealThermometerSource` does not implement the
optional `ThermometerSimControls`.

### 5. Two things the adapter must handle that the mock fakes for free

- **"Switch off" as a disconnect.** A truly powered-off box sends nothing, so
  the adapter needs a **staleness watchdog**: if no frame arrives for ~3 s,
  synthesize frames with `switchState: 'off'` so the console shows
  "no data available" and the chart gaps. When frames resume, real data flows
  again — this is what satisfies the spec's "recover within 10 s" requirement.
  (If the box has a *soft* switch that keeps the radio alive, it can just report
  `switchState: 'off'` directly and the watchdog is a backup.)
- **Clock skew.** The chart's X-axis uses frame timestamps. If the box clock is
  unreliable, have the adapter stamp `timestamp = Date.now()` on arrival
  instead of trusting the box.

### 6. Where the app and the box run

The console is a static site. On demo day, from `frontend/` run `npm run dev` (or serve
`npm run build` output) on the lab computer, with the box on the **same LAN**.
Note: a browser page served over **https** cannot open an insecure `ws://` — so
either serve the console over plain `http` on the LAN, or terminate `wss://`
with a certificate on the box/broker.

### Phone / email alert delivery

SMS delivery is implemented: see [Running with SMS alerts](#running-with-sms-alerts).
Default `console` mode needs no API keys. Real Twilio send is optional (`SMS_MODE=live`).

Email delivery is still out of scope.

---

## Assumptions / judgement calls (worth confirming with the instructor)

1. **"Display off" (virtual button off)** is shown as its own readout message
   (`display off`) and as a missing-data gap on the chart. The spec names the
   unplugged and switch-off cases explicitly but not this one.
2. **Missing-data bands are per-sensor and full plot height**, tinted in that
   sensor's colour, so a one-sensor outage doesn't look like a total outage.
3. **Alerts + missing data:** a sensor that goes offline while exceeding a
   threshold and returns still-exceeded does **not** re-alert — missing data is
   not treated as returning to the safe band.
4. **Thresholds are stored in Celsius** and converted for display; editing in
   °F round-trips through Celsius (minor display rounding).
5. **Alert destination** is a free-text field with no validation; nothing is
   sent in this MVP.
6. **Tooling:** added `vitest` + `jsdom` as dev dependencies for the test suite
   (the original brief suggested a plain React app).

---

## Stack

Vite + React + TypeScript. The chart recorder is drawn by hand on a `<canvas>`
(no charting library) so the fixed axis, right-to-left scroll, and the
missing-vs-off-scale rendering behave exactly as the spec requires.


---

## Firmware, protocol, and Python connector


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
object with that interface. A reference implementation against this project's
schema ships at [pc_client/mysql_adapter.py](backend/pc_client/mysql_adapter.py)
(SCRUM-341/368/369). It requires a MySQL server already running somewhere
reachable — it's a client only, it does not start one itself:

```powershell
$env:THERMOMETER_DATABASE_ADAPTER_FACTORY = "pc_client.mysql_adapter:create_adapter"
$env:THERMOMETER_DB_HOST = "127.0.0.1"      # defaults shown; only set what differs
$env:THERMOMETER_DB_PORT = "3306"
$env:THERMOMETER_DB_USER = "root"
$env:THERMOMETER_DB_PASSWORD = "..."
$env:THERMOMETER_DB_NAME = "thermometer"
.venv\Scripts\python main.py
```

No ESP32 required to exercise this path end-to-end:
[pc_client/mock_run.py](backend/pc_client/mock_run.py) runs the real service
against a simulated thermometer (`python -m pc_client.mock_run`), so rows can
be confirmed landing in MySQL before real firmware is available.

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
