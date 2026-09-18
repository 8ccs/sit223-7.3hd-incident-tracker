<#
.SYNOPSIS
  Deploy (staging) / Release (production) stage.
  Extracts the SAME versioned artifact zip into an environment-isolated
  directory, provisions a venv, writes environment-specific config, stops
  any previously running process for that environment, starts the new
  one, and waits for /health to report ok (readiness check).

  Staging and production never share a directory, port, database file or
  process, so promoting to production cannot overwrite staging (or vice
  versa), and this script never touches any directory outside its own
  environment root.

.PARAMETER Environment
  "staging" or "production".

.PARAMETER ZipPath
  Path to the artifact zip produced by package_artifact.ps1. The SAME
  zip is used for both staging and production releases: Release never
  rebuilds the app.

.PARAMETER AlertWebhookUrl
  Optional. Passed in from a Jenkins credential (secret text), never
  hardcoded. Falls back to the local webhook inbox used for development.
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet("staging", "production")][string]$Environment,
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [string]$Root = "C:\devops-demo",
    [string]$AlertWebhookUrl = "http://localhost:9099/webhook"
)

$ErrorActionPreference = "Stop"

$envRoot = Join-Path $Root $Environment
$releasesDir = Join-Path $envRoot "releases"
$currentLink = Join-Path $envRoot "current"
$lockFile = Join-Path $envRoot "deploy.lock"
$dataDir = Join-Path $envRoot "data"
$logsDir = Join-Path $envRoot "logs"
$port = if ($Environment -eq "staging") { 5001 } else { 5000 }

New-Item -ItemType Directory -Path $envRoot, $releasesDir, $dataDir, $logsDir -Force | Out-Null

# --- overlap protection -----------------------------------------------
if (Test-Path $lockFile) {
    $age = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    if ($age.TotalMinutes -lt 15) {
        throw "Another deployment to '$Environment' appears to be in progress (lock file is $([int]$age.TotalMinutes) min old). Aborting to avoid overlapping deployments."
    }
    Write-Warning "Stale lock file found (age $([int]$age.TotalMinutes) min); removing it."
    Remove-Item $lockFile -Force
}
New-Item -ItemType File -Path $lockFile -Force | Out-Null

try {
    if (-not (Test-Path $ZipPath)) { throw "Artifact not found: $ZipPath" }
    $zipName = Split-Path $ZipPath -Leaf
    $versionDir = Join-Path $releasesDir ([System.IO.Path]::GetFileNameWithoutExtension($zipName))

    Write-Host "Deploying $zipName to $Environment (port $port)"

    if (Test-Path $versionDir) { Remove-Item $versionDir -Recurse -Force }
    New-Item -ItemType Directory -Path $versionDir | Out-Null
    Expand-Archive -Path $ZipPath -DestinationPath $versionDir -Force

    # --- venv (created once per environment, reused across releases) ---
    $venvDir = Join-Path $envRoot "venv"
    if (-not (Test-Path $venvDir)) {
        Write-Host "Creating venv for $Environment"
        # "python" is not on PATH for every caller (notably the Jenkins
        # LocalSystem service account, which has no user-level PATH
        # entries), so fall back to the known per-user install if the
        # bare command can't be resolved.
        $systemPython = (Get-Command python -ErrorAction SilentlyContinue).Source
        if (-not $systemPython) {
            $systemPython = "C:\Users\auwal\AppData\Local\Programs\Python\Python311\python.exe"
        }
        & $systemPython -m venv $venvDir
    }
    $pip = Join-Path $venvDir "Scripts\pip.exe"
    $pythonExe = Join-Path $venvDir "Scripts\python.exe"
    & $pip install --quiet --disable-pip-version-check -r (Join-Path $versionDir "requirements.txt")

    # --- record previous version for rollback, before we overwrite "current" ---
    $versionFile = Join-Path $envRoot "current_version.txt"
    if (Test-Path $versionFile) {
        Copy-Item $versionFile (Join-Path $envRoot "previous_version.txt") -Force
    }
    Set-Content -Path $versionFile -Value $zipName -Encoding utf8

    # --- environment config (non-secret values checked in as .example, ---
    # --- secret-like value injected from Jenkins credential at deploy time) ---
    $manifest = Get-Content (Join-Path $versionDir "version.json") | ConvertFrom-Json
    $envFile = Join-Path $envRoot "current.env"
    @"
APP_ENV=$Environment
PORT=$port
DB_PATH=$dataDir\incidents.db
APP_VERSION=$($manifest.full_version)
GIT_COMMIT=$($manifest.git_commit)
ALERT_WEBHOOK_URL=$AlertWebhookUrl
"@ | Set-Content -Path $envFile -Encoding utf8

    # --- stop previous process for this environment, if any ---
    $pidFile = Join-Path $envRoot "app.pid"
    if (Test-Path $pidFile) {
        $oldPid = Get-Content $pidFile
        Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    # Safety net: also free the port if something else is bound to it.
    $existing = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $existing) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
    $stillListening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($stillListening) {
        # Most likely cause: the previous process was started by Jenkins
        # (LocalSystem) and this caller does not have permission to stop a
        # SYSTEM-owned process. An elevated ("Run as Administrator")
        # window can; Jenkins itself always can, since it IS SYSTEM.
        throw "Port $port is still in use by pid $($stillListening[0].OwningProcess) and it could not be stopped. If that process was deployed by Jenkins, it runs as SYSTEM -- re-run this from an elevated PowerShell window (Run as Administrator), or redeploy via Jenkins itself."
    }

    # --- start new process ---
    $env:APP_ENV = $Environment
    $env:PORT = "$port"
    $env:DB_PATH = "$dataDir\incidents.db"
    $env:APP_VERSION = $manifest.full_version
    $env:GIT_COMMIT = $manifest.git_commit

    $stdout = Join-Path $logsDir "app.out.log"
    $stderr = Join-Path $logsDir "app.err.log"
    $waitress = Join-Path $venvDir "Scripts\waitress-serve.exe"
    # Bound to localhost only: Jenkins, Prometheus, and the browser all run
    # on this same machine for the local demo, so there is no need to
    # expose the app on every network interface (see app/app.py B104 note).
    $arguments = @("--listen=127.0.0.1:$port", "--call", "app.app:create_app")

    # All three standard streams are explicitly redirected to files (stdin
    # from a permanent empty file -- Start-Process requires an existing
    # file on a filesystem provider, so the "\\.\NUL" device path is
    # rejected). Without this, the new process can inherit the CALLER's
    # own stdout/stderr handles on Windows -- when the caller is itself a
    # piped process (a Jenkins pipeline step, or Python's subprocess.run
    # with captured output), that caller then waits forever for
    # end-of-pipe, which never comes because this long-lived detached
    # server keeps its inherited copy of the handle open. This hung both
    # an earlier Jenkins build and scripts/verify_alert_path.py before
    # the redirection was added here and (for the Python side) in that
    # script.
    $emptyStdin = Join-Path $Root "empty.stdin"
    if (-not (Test-Path $emptyStdin)) {
        New-Item -ItemType Directory -Path $Root -Force | Out-Null
        New-Item -ItemType File -Path $emptyStdin -Force | Out-Null
    }

    Push-Location $versionDir
    try {
        $proc = Start-Process -FilePath $waitress -ArgumentList $arguments `
            -WorkingDirectory $versionDir -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
            -RedirectStandardInput $emptyStdin
        Set-Content -Path $pidFile -Value $proc.Id -Encoding ascii
    } finally {
        Pop-Location
    }

    # --- readiness check: poll /health until it reports ok ---
    $healthUrl = "http://localhost:$port/health"
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            $resp = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
            if ($resp.status -eq "ok") { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) {
        throw "Deployment to $Environment failed readiness check at $healthUrl after 30s. See $stderr"
    }
    Write-Host "$Environment is ready: $healthUrl -> ok (pid $($proc.Id), version $($manifest.full_version))"
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}
