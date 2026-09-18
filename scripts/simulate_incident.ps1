<#
.SYNOPSIS
  Reversible local incident simulation for the Monitoring stage demo.
  Stops the production app process (keeping its data files untouched),
  which makes Prometheus's `up` metric for the production target go to 0.
  This is scoped ONLY to this project's own production process on its own
  port; it never touches any other service, container, or real system.

  Run scripts/recover_incident.ps1 afterwards to restart it.
#>
param(
    [string]$Root = "C:\devops-demo",
    [string]$Environment = "production"
)

$ErrorActionPreference = "Stop"
$envRoot = Join-Path $Root $Environment
$pidFile = Join-Path $envRoot "app.pid"

if (-not (Test-Path $pidFile)) {
    throw "No running $Environment process found (missing $pidFile). Deploy/release first."
}

$targetPid = Get-Content $pidFile
Write-Host "Simulating an incident: stopping $Environment app (pid $targetPid)."
Write-Host "Data files under $envRoot\data are left untouched."
Stop-Process -Id $targetPid -Force
Write-Host "Stopped. Prometheus will mark the '$Environment' target down after its next scrape."
Write-Host "Run scripts\recover_incident.ps1 to restore service."
