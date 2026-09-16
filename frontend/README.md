# Computer console

Vite + React UI for the ECE:4880 networked thermometer. This is the
`frontend/` folder the repo layout reserved for the web app.

## Run

From **this directory**:

```bash
npm install
npm run dev
```

Open <http://localhost:5173>. Defaults to mock sensor data.

| Command | Purpose |
| --- | --- |
| `npm run dev` | Vite UI on `:5173` plus the Node alert/sample service on `:8787` |
| `npm test` | Unit tests |
| `npm run build` | Type-check + production build into `dist/` |
| `npm run lint` | oxlint |

From the **repository root**, `bash scripts/setup.sh` (or `scripts/setup.ps1`)
installs this package, copies env templates, and can create `backend/.venv`.

## BLE

Create `frontend/.env` from `.env.example` and set `VITE_DATA_SOURCE=ble`.
Restart `npm run dev`. Start `backend/main.py` separately. Full Scan → PIN →
Connect steps are in the repository root [README](../README.md#connecting-the-console-to-ble-and-mysql).
