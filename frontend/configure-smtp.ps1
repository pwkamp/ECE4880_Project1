param(
    [string]$Email
)

$ErrorActionPreference = "Stop"
$FrontendDir = $PSScriptRoot
$BackendDir = [System.IO.Path]::GetFullPath((Join-Path $FrontendDir "..\backend"))
$EnvFile = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $BackendDir ".env.example"

function Fail([string]$Message) {
    throw "frontend/configure-smtp.ps1: $Message"
}

function Set-DotEnvValue([string]$Path, [string]$Name, [string]$Value) {
    $Lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $Path) {
        foreach ($Line in Get-Content -LiteralPath $Path) { $Lines.Add($Line) }
    }
    $Pattern = "^\s*" + [Regex]::Escape($Name) + "="
    $Found = $false
    for ($Index = 0; $Index -lt $Lines.Count; $Index++) {
        if ($Lines[$Index] -match $Pattern) {
            $Lines[$Index] = "$Name=$Value"
            $Found = $true
            break
        }
    }
    if (-not $Found) { $Lines.Add("$Name=$Value") }
    [System.IO.File]::WriteAllLines($Path, $Lines, [System.Text.UTF8Encoding]::new($false))
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    if (-not (Test-Path -LiteralPath $EnvExample)) { Fail "missing $EnvExample" }
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
}

if ([string]::IsNullOrWhiteSpace($Email)) {
    $Email = Read-Host "Gmail address used to send thermometer alerts"
}
try {
    $Parsed = [System.Net.Mail.MailAddress]::new($Email.Trim())
}
catch {
    Fail "enter a valid Gmail address"
}
if ($Parsed.Address -ne $Email.Trim()) { Fail "enter one plain Gmail address" }

$SecurePassword = Read-Host "Google App Password (input hidden; do not use your normal password)" -AsSecureString
$PasswordPointer = [IntPtr]::Zero
try {
    $PasswordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
    $AppPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($PasswordPointer)
}
finally {
    if ($PasswordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($PasswordPointer)
    }
}
$AppPassword = ($AppPassword -replace '\s', '')
if ($AppPassword.Length -lt 16) {
    Fail "the Google App Password is missing or too short; create a 16-character App Password in your Google account"
}

Set-DotEnvValue $EnvFile "EMAIL_MODE" "live"
Set-DotEnvValue $EnvFile "SMTP_HOST" "smtp.gmail.com"
Set-DotEnvValue $EnvFile "SMTP_PORT" "465"
Set-DotEnvValue $EnvFile "SMTP_SECURE" "true"
Set-DotEnvValue $EnvFile "SMTP_USER" $Parsed.Address
Set-DotEnvValue $EnvFile "SMTP_PASS" $AppPassword
Set-DotEnvValue $EnvFile "SMTP_FROM" $Parsed.Address

$AppPassword = $null
Write-Host "Live Gmail SMTP is configured in the gitignored backend/.env."
Write-Host "Restart frontend/run.ps1 so Docker rebuilds/recreates the frontend service with EMAIL_MODE=live."
