# Install console + BLE connector dependencies if they are missing.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Need Node.js 20+ (https://nodejs.org)."
}

if (-not (Test-Path "node_modules")) {
    npm install
} else {
    Write-Host "node_modules already present; skipping npm install"
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Wrote .env from .env.example (default mock data)."
}
if ((-not (Test-Path "server/.env")) -and (Test-Path "server/.env.example")) {
    Copy-Item "server/.env.example" "server/.env"
    Write-Host "Wrote server/.env from server/.env.example."
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    if (-not (Test-Path "backend/.venv")) {
        python -m venv backend/.venv
    }
    & "backend/.venv/Scripts/python.exe" -m pip install -r backend/pc_client/requirements.txt
    Write-Host "Python BLE venv ready. From backend/: .venv\Scripts\python.exe main.py"
} else {
    Write-Host "Python not found; skipped BLE venv. Console mock data still works."
}

Write-Host ""
Write-Host "Start the console:  npm run dev"
Write-Host "BLE mode:           set VITE_DATA_SOURCE=ble in .env, restart npm run dev,"
Write-Host "                    and run backend/main.py in a second terminal."
Write-Host "Host Bluetooth is required for a real ESP32; that is why this is not Dockerized."
