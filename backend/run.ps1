param([switch]$KeepDatabase)

# Not "Stop": docker compose/mysql write normal progress and warnings to
# stderr (image pulls, container start/stop, "using a password on the
# command line" notices), and PowerShell 5.1 treats any stderr line from a
# native command as a terminating error under "Stop", regardless of exit
# code. Every native call below is already checked explicitly via
# $LASTEXITCODE, and Fail() uses `throw`, which terminates unconditionally
# either way, so "Stop" was never load-bearing for this script's own error
# handling -- only for misreading normal Docker output as fatal.
$ErrorActionPreference = "Continue"

$BackendDir = $PSScriptRoot
$ComposeFile = Join-Path $BackendDir "compose.yaml"
$EnvFile = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $BackendDir ".env.example"
$RuntimeDir = Join-Path $BackendDir ".runtime"
$VenvDir = Join-Path $BackendDir ".venv"

function Fail([string]$Message) {
    throw "backend/run.ps1: $Message"
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

function Require-Setting($Settings, [string]$Name) {
    if (-not $Settings.ContainsKey($Name) -or [string]::IsNullOrWhiteSpace($Settings[$Name])) {
        Fail "$Name must be set in $EnvFile"
    }
}

function Invoke-Compose([string[]]$Arguments) {
    & docker compose @ComposeBase @Arguments
    if ($LASTEXITCODE -ne 0) { Fail "docker compose command failed" }
}

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    Fail "the native WinRT backend launcher requires Windows"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker Desktop is not installed or docker is not on PATH"
}
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Fail "the Docker Compose plugin is not installed" }
& docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker Desktop is not running or is not using Linux containers" }

$BluetoothService = Get-Service -Name bthserv -ErrorAction SilentlyContinue
if (-not $BluetoothService) { Fail "the Windows Bluetooth service is unavailable" }
if ($BluetoothService.Status -ne "Running") {
    Fail "the Windows Bluetooth service is not running"
}
if (Get-Command Get-PnpDevice -ErrorAction SilentlyContinue) {
    $BluetoothDevices = @(Get-PnpDevice -Class Bluetooth -Status OK -ErrorAction SilentlyContinue)
    if ($BluetoothDevices.Count -eq 0) {
        Fail "no enabled Windows Bluetooth device was found"
    }
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    Write-Host "Created $EnvFile from .env.example with local-development defaults."
}
$Config = Read-DotEnv $EnvFile
foreach ($Name in @(
    "COMPOSE_PROJECT_NAME", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD",
    "MYSQL_ROOT_PASSWORD", "MYSQL_HOST_PORT", "BACKEND_PORT",
    "WINDOWS_BLE_API_BASE", "WINDOWS_CORS_ORIGINS"
)) {
    Require-Setting $Config $Name
}
if ($Config["MYSQL_DATABASE"] -ne "thermometer") {
    Fail "MYSQL_DATABASE must remain thermometer because database/schema.sql owns that name"
}

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCommand) { Fail "Python 3.10 or newer is required" }
$PythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) { Fail "Python could not be started" }
$VersionParts = $PythonVersion.Split(".")
if ([int]$VersionParts[0] -lt 3 -or ([int]$VersionParts[0] -eq 3 -and [int]$VersionParts[1] -lt 10)) {
    Fail "Python 3.10 or newer is required (found $PythonVersion)"
}

$ComposeBase = @(
    "--project-name", $Config["COMPOSE_PROJECT_NAME"],
    "--env-file", $EnvFile,
    "--file", $ComposeFile
)
Invoke-Compose @("config", "--quiet")

if (-not $KeepDatabase) {
    Write-Host "Stopping the integration stack and deleting its MySQL volume..."
    Invoke-Compose @("down", "--volumes", "--remove-orphans")
} else {
    Write-Host "Keeping the existing MySQL volume and its temperature history."
}

foreach ($PortName in @("BACKEND_PORT")) {
    $Port = [int]$Config[$PortName]
    $Listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($Listener) { Fail "TCP port $Port is already in use" }
}
if (-not $KeepDatabase) {
    $Port = [int]$Config["MYSQL_HOST_PORT"]
    $Listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($Listener) { Fail "TCP port $Port is already in use" }
}

Write-Host "Starting a fresh MySQL database on 127.0.0.1:$($Config['MYSQL_HOST_PORT'])..."
Invoke-Compose @("up", "--build", "--detach", "mysql")

$RunningServices = @(& docker compose @ComposeBase ps --services)
if ($RunningServices -contains "backend") {
    Fail "the Windows launcher unexpectedly created the Linux backend container"
}
$MySqlContainer = ((& docker compose @ComposeBase ps --quiet mysql) | Out-String).Trim()
if (-not $MySqlContainer) { Fail "the MySQL container was not created" }

$MySqlHealthy = $false
for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
    $Health = ((& docker inspect --format "{{.State.Health.Status}}" $MySqlContainer 2>$null) | Out-String).Trim()
    if ($Health -eq "healthy") {
        $MySqlHealthy = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $MySqlHealthy) {
    & docker compose @ComposeBase logs mysql
    Fail "MySQL did not become healthy"
}

$Count = ((& docker compose @ComposeBase exec -T mysql mysql `
    "--user=$($Config['MYSQL_USER'])" `
    "--password=$($Config['MYSQL_PASSWORD'])" `
    $Config["MYSQL_DATABASE"] `
    --batch --skip-column-names `
    "--execute=SELECT COUNT(*) FROM temperature_samples;") | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    Fail "MySQL temperature_samples could not be queried"
}
if (-not $KeepDatabase -and $Count -ne "0") {
    Fail "fresh MySQL schema did not contain exactly zero temperature rows (found $Count)"
}
if ($KeepDatabase) {
    Write-Host "Existing MySQL schema verified: temperature_samples contains $Count rows."
} else {
    Write-Host "Fresh MySQL schema verified: temperature_samples contains 0 rows."
}

if (-not (Test-Path -LiteralPath $VenvDir)) {
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Fail "could not create $VenvDir" }
}
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $BackendDir "pc_client\requirements-dev.txt")
if ($LASTEXITCODE -ne 0) { Fail "Python dependencies could not be installed" }

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
$env:THERMOMETER_API_HOST = "127.0.0.1"
$env:THERMOMETER_API_PORT = $Config["BACKEND_PORT"]
$env:THERMOMETER_DATABASE_ADAPTER_FACTORY = "pc_client.mysql_adapter:create_adapter"
$env:THERMOMETER_DB_HOST = "127.0.0.1"
$env:THERMOMETER_DB_PORT = $Config["MYSQL_HOST_PORT"]
$env:THERMOMETER_DB_USER = $Config["MYSQL_USER"]
$env:THERMOMETER_DB_PASSWORD = $Config["MYSQL_PASSWORD"]
$env:THERMOMETER_DB_NAME = $Config["MYSQL_DATABASE"]
$env:THERMOMETER_CREDENTIAL_REGISTRY_PATH = Join-Path $RuntimeDir "paired_devices.csv"
$env:THERMOMETER_CORS_ORIGINS = $Config["WINDOWS_CORS_ORIGINS"]

Write-Host "Starting the native WinRT BLE backend on http://127.0.0.1:$($Config['BACKEND_PORT'])"
Push-Location $BackendDir
try {
    & $VenvPython "main.py"
    if ($LASTEXITCODE -ne 0) { Fail "the native backend exited with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
