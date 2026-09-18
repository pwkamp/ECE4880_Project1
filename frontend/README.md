# Computer console

Vite + React UI for the ECE:4880 networked thermometer. This is the
`frontend/` folder the repo layout reserved for the web app.

## Run

From **this directory**:

```bash
npm install
npm run dev
```

Open <http://localhost:5173>.

| Command | Purpose |
| --- | --- |
| `npm run dev` | Vite UI on `:5173` plus the Node alert/sample service on `:8787` |
| `npm test` | Unit tests |
| `npm run build` | Type-check + production build into `dist/` |
| `npm run lint` | oxlint |

From the **repository root**, `bash scripts/setup.sh` (or `scripts/setup.ps1`)
installs this package, copies env templates, and can create `backend/.venv`.

## Cross-platform integration

Start the backend path for the host OS:

```powershell
.\backend\run.ps1
```

```bash
bash backend/run.sh
```

Then, from a second terminal, start this web application:

```powershell
.\frontend\run.ps1
```

```bash
bash frontend/run.sh
```

The frontend script uses `backend/compose.yaml` and the same gitignored
`backend/.env` as the other services. Vite runs on
<http://127.0.0.1:5173>. Linux proxies `/api/v1` to the BlueZ backend
container. Windows sets `VITE_BLE_API_BASE` so the browser calls the native
WinRT backend on loopback. Both paths proxy `/api` to the Node sample reader
in the frontend container, which connects to MySQL over the private Compose
network. Full ESP32 flashing, pairing, and data-flow checks are documented in
[`docs/integration-test.md`](../docs/integration-test.md).

The browser reads temperatures and the rolling graph exclusively from MySQL
through `/api/samples`. It polls backend status for connection and confirmed
display states, but never requests an ESP32 current or history transaction.
The backend performs those transactions, including history recovery after
reconnection. Scan fills a device dropdown; the single **Connect** button
uses a saved credential when available or prompts for the six-digit PIN.
Display toggles lock until the ESP32 confirms the command, and **Disconnect**
explicitly stops the backend BLE connection/retry intent.

For non-container development, `VITE_BLE_API_BASE`, `BACKEND_PROXY_TARGET`,
`FRONTEND_SERVER_PROXY_TARGET`, and `FRONTEND_HOST` may override the browser
BLE endpoint and Vite targets/bind. An empty `VITE_BLE_API_BASE` preserves the
relative Linux proxy path.

## BLE

Create `frontend/.env` from `.env.example` and set `VITE_DATA_SOURCE=ble`.
Restart `npm run dev`. Start `backend/main.py` separately. Full Scan → PIN →
Connect steps are in the repository root [README](../README.md#connecting-the-console-to-ble-and-mysql).
