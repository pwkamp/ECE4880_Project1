$ErrorActionPreference = "Stop"

$FrontendDir = $PSScriptRoot
$BackendDir = [System.IO.Path]::GetFullPath((Join-Path $FrontendDir "..\backend"))
$ComposeFile = Join-Path $BackendDir "compose.yaml"
$EnvFile = Join-Path $BackendDir ".env"

function Fail([string]$Message) {
    throw "frontend/run.ps1: $Message"
}

function Read-DotEnv([string]$Path) {
    $Values = @{}
    foreach ($Line in Get-Content -LiteralPath $Path) {
        $Trimmed = $Line.Trim()
        if (-not $Trimmed -or $Trimmed.StartsWith("#")) { continue }
        $Parts = $Trimmed.Split(@("="), 2, [System.StringSplitOptions]::None)
        if ($Parts.Count -eq 2) {
            $Values[$Parts[0].Trim()] = $Parts[1].Trim().Trim('"').Trim("'")
        }
    }
    return $Values
}

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    Fail "the native WinRT frontend launcher requires Windows"
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Fail "run backend/run.ps1 first so $EnvFile is created"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker Desktop is not installed or docker is not on PATH"
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker Desktop is not running" }

$Config = Read-DotEnv $EnvFile
foreach ($Name in @(
    "COMPOSE_PROJECT_NAME", "BACKEND_PORT", "FRONTEND_PORT", "WINDOWS_BLE_API_BASE"
)) {
    if (-not $Config.ContainsKey($Name) -or [string]::IsNullOrWhiteSpace($Config[$Name])) {
        Fail "$Name must be set in $EnvFile"
    }
}

$BackendHealthUrl = "http://127.0.0.1:$($Config['BACKEND_PORT'])/healthz"
try {
    $Health = Invoke-RestMethod -Uri $BackendHealthUrl -Method Get -TimeoutSec 5
}
catch {
    Fail "the native backend is unreachable at $BackendHealthUrl; keep backend/run.ps1 running"
}
if (-not $Health.ready -or -not $Health.persistence_configured -or -not $Health.database_adapter_available) {
    Fail "the native backend is not ready with MySQL persistence"
}
try {
    $BleStatus = Invoke-RestMethod -Uri "http://127.0.0.1:$($Config['BACKEND_PORT'])/api/v1/ble/status" -Method Get -TimeoutSec 5
}
catch {
    Fail "the native BLE status endpoint is unreachable"
}
if ($BleStatus.host_os -ne "windows" -or $BleStatus.pairing_backend -ne "winrt") {
    Fail "the running backend is not the native Windows/WinRT service"
}

$FrontendPort = [int]$Config["FRONTEND_PORT"]
$Listener = Get-NetTCPConnection -State Listen -LocalPort $FrontendPort -ErrorAction SilentlyContinue
if ($Listener) { Fail "TCP port $FrontendPort is already in use" }

$env:VITE_BLE_API_BASE = $Config["WINDOWS_BLE_API_BASE"]
$ComposeBase = @(
    "--project-name", $Config["COMPOSE_PROJECT_NAME"],
    "--env-file", $EnvFile,
    "--file", $ComposeFile
)
& docker compose @ComposeBase config --quiet
if ($LASTEXITCODE -ne 0) { Fail "Docker Compose configuration is invalid" }
$RunningServices = @(& docker compose @ComposeBase ps --services)
if ($RunningServices -contains "backend") {
    Fail "the Windows launcher found an unexpected Linux backend container"
}

Write-Host "Starting the web console on http://127.0.0.1:$FrontendPort"
& docker compose @ComposeBase up --build --no-deps frontend
if ($LASTEXITCODE -ne 0) { Fail "the frontend container exited with code $LASTEXITCODE" }
