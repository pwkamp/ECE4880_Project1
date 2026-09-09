# Networked Thermometer — Computer Console

The **computer** component of the ECE:4880 dual-sensor networked thermometer
system.

> The console defaults to **mock data**. Point it at the teammate Python BLE
> connector with `VITE_DATA_SOURCE=ble` (see
> [Python BLE connector](#python-ble-connector)).

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

**Prerequisites:** Node.js 20+ and npm (developed on Node 24).

```bash
npm install
npm run dev
```

Open the URL Vite prints — default <http://localhost:5173>. The chart is
pre-seeded with 300 s of history, so it's full immediately. Hot-reloads on
save; `Ctrl+C` stops it.

| Command | Purpose |
| --- | --- |
| `npm run dev` | Run the console in development |
| `npm test` | Unit tests: alert logic, readout logic, mock data source, an App render smoke test (13 tests) |
| `npm run build` | Type-check + production build into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | oxlint |

No cloud services, API keys, or internet access are required for the default
console (mock data + logged SMS).

The web console is the product. `npm run dev` is how you run it. BLE and MySQL
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
| Web console | `npm run dev` (Vite half) | `http://localhost:5173` | UI: readouts, chart, scan/connect panel, alerts |
| Alert + sample reader | `npm run dev` (started automatically) | `127.0.0.1:8787` | SMS delivery; **reads** `temperature_samples` when `MYSQL_URL` is set |
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
- **Bluetooth adapter** on the PC. Automatic PIN pairing is implemented for
  **Windows 10/11**. Linux/macOS can often scan/connect with Bleak, but the
  Windows pairing helper will not run; you may have to pair in the OS Bluetooth
  settings and type the six-digit passkey there.
- **MySQL 8** if you want the chart seeded from the database (optional for a
  first BLE bring-up).
- **One Python connector at a time.** It owns the BLE adapter and scans in a
  loop. A second copy, or leaving it running while hammering scan, can lock up
  the Bluetooth stack (especially on Linux).

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

The **reader** URL goes in `server/.env` (this repo’s Node service):

```
MYSQL_URL=mysql://thermo:pick-a-password@127.0.0.1:3306/thermometer
```

Copy `server/.env.example` → `server/.env` if you do not have one yet.
`server/.env` is gitignored.

The **writer** is not this Node URL. Python loads

```
THERMOMETER_DATABASE_ADAPTER_FACTORY=your.package.module:create_adapter
```

in the environment **before** `python main.py`. The factory must return an
object that implements `ThermometerDatabaseAdapter` in
`backend/pc_client/database_adapter.py` (`publish_current_sample`,
`upsert_history`, etc.). Until the DB teammate ships that module, Python uses
`NoOpDatabaseAdapter`: it accepts every write and stores nothing.
`GET /healthz` will show `"persistence_configured": false`. The console will
then use `/api/v1/ble/current` instead of MySQL. That is expected.

Confirm the reader without the UI:

```bash
# after npm run dev is up, or curl the Node port directly
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

On startup the service **already scans** in the background. With one known
device it will try to pair/connect by itself. Zero devices stay in
`DISCOVERING`. Several unknown devices go to `SELECTION_REQUIRED` and you pick
one from the console.

Successful enrollment writes gitignored `backend/paired_devices.csv` (plaintext
per-device credentials). Do not commit it.

Optional Tk hardware tool (not the web UI):

```bash
.venv/bin/python -m pc_client.gui
```

### 3. Point the web console at BLE (the web app is still required)

The console **defaults to mock data** so `npm run dev` alone still works for UI
work. To use the Python service, create a **repo-root** `.env` (gitignored;
Vite only reads it at startup):

```
VITE_DATA_SOURCE=ble
```

There is a template in [`.env.example`](.env.example). Then:

```bash
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

If you change `.env`, restart Vite. `VITE_*` values are baked in at dev-server
start.

### 4. Connect a thermometer from the UI

1. Power the ESP32; wait until it advertises.
2. Click **Scan**. You want a name like `Thermometer-A1B2C3` and a MAC.
3. If the service returns 401 / “authentication required”, enter the firmware
   six-digit passkey and click **Connect** on that row.
4. Watch **Device connection** status:
   - `DISCOVERING` — no box (or BLE adapter unhappy)
   - `PAIRING` / `CONNECTING` / `VERIFYING` — in progress
   - `CONNECTED` with `(ready)` — protocol auth + first snapshot succeeded
   - `AUTHENTICATION_REQUIRED` / `SELECTION_REQUIRED` — you need to act
   - `RECONNECTING` — radio dropped; it will retry
5. Use **Sensor display** checkboxes as the virtual buttons (`PUT /displays/1`
   and `/displays/2`).
6. Readouts and the 300 s chart should move. If MySQL is wired they come from
   `temperature_samples`; otherwise from `/api/v1/ble/current`.

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

### 5. Checklist: “is it actually connected?”

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
| Subtitle still says mock; no Device panel | Root `.env` missing `VITE_DATA_SOURCE=ble`, or Vite not restarted |
| Device panel: scan fails / proxy errors | Python not running on `:8000`, or a second process stole the port |
| Phase stuck on `DISCOVERING` | ESP32 off, out of range, wrong firmware name prefix, or PC Bluetooth disabled |
| `401` on connect | Passkey missing/wrong; must match `firmware/device_config.cmake` |
| `409` | Connector is busy (already connected / conflicting scan) |
| Chart empty but status `ready` | Displays off, both probes disconnected, or `/current` has nulls |
| Chart empty, `persistence_configured: false`, and `/current` also empty | No BLE snapshot yet — not a MySQL problem |
| `MYSQL_URL` set but `/api/samples/latest` is 503 | Wrong password, MySQL down, or schema not applied |
| Samples configured but row always null | Writer adapter still no-op, or history never synced |
| Machine/Bluetooth hard-locks | Two `main.py` processes, or aggressive scanning on Linux — run **one** connector and stop it when you are done (`Ctrl+C`) |
| Browser CORS errors to `:8000` | You called Python from the page without the Vite proxy. Use relative `/api/v1/...` |

### Switching back to mock data

Remove `VITE_DATA_SOURCE=ble` from `.env` (or set it to anything other than
`ble`) and restart `npm run dev`. You do not need Python or MySQL. Demo
controls come back. This is the default for UI work.

## Running with SMS alerts

`npm run dev` starts the web app **and** a small delivery service
(`server/`, on `127.0.0.1:8787`). The browser evaluates alerts against the
mock sensor data as usual and POSTs each HIGH/LOW transition to the service.

Delivery mode is set by `server/.env` (copy from `server/.env.example`):

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

If `ALERT_API_TOKEN` is set in `server/.env`, also set
`VITE_ALERT_API_TOKEN` (same value) in a root `.env` file so the frontend
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

The console is a static site. On demo day, run `npm run dev` (or serve
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
