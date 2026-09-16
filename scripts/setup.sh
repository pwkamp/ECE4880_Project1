#!/usr/bin/env bash
# Install console + BLE connector dependencies if they are missing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v node >/dev/null 2>&1; then
  echo "Need Node.js 20+ (https://nodejs.org)." >&2
  exit 1
fi

if [ ! -d node_modules ]; then
  npm install
else
  echo "node_modules already present; skipping npm install"
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Wrote .env from .env.example (default mock data)."
fi
if [ ! -f server/.env ] && [ -f server/.env.example ]; then
  cp server/.env.example server/.env
  echo "Wrote server/.env from server/.env.example."
fi

PYTHON=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
fi

if [ -n "$PYTHON" ]; then
  if [ ! -d backend/.venv ]; then
    "$PYTHON" -m venv backend/.venv
  fi
  # shellcheck disable=SC1091
  if [ -x backend/.venv/bin/pip ]; then
    backend/.venv/bin/pip install -r backend/pc_client/requirements.txt
  elif [ -x backend/.venv/Scripts/pip.exe ]; then
    backend/.venv/Scripts/pip.exe install -r backend/pc_client/requirements.txt
  fi
  echo "Python BLE venv ready. From backend/: .venv/bin/python main.py"
else
  echo "Python not found; skipped BLE venv. Console mock data still works."
fi

echo
echo "Start the console:  npm run dev"
echo "BLE mode:           set VITE_DATA_SOURCE=ble in .env, restart npm run dev,"
echo "                    and run backend/main.py in a second terminal."
echo "Host Bluetooth is required for a real ESP32; that is why this is not Dockerized."
