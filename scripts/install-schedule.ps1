<#
.SYNOPSIS
    Register a Windows Scheduled Task that runs a bounded voidbroker ingest on a cadence.

.DESCRIPTION
    The archive only becomes a moat if ingestion runs unattended. This registers a
    repeating one-shot `voidbroker ingest` (tiered, resumable) rather than babysitting a
    long-lived process: it survives reboots, each run is isolated, and the stalest refs
    rotate so the whole catalog is swept over time.

    Registration uses schtasks.exe (the classic COM-based tool), which works for a
    current-user task without elevation on most machines. The PowerShell
    ScheduledTasks cmdlets talk to Task Scheduler over WMI and are often blocked by ACLs
    in a non-admin session (HRESULT 0x80070005); schtasks avoids that path.

.PARAMETER IntervalHours
    Hours between runs. Default 6. Fractional values are converted to a minute cadence.

.PARAMETER Batch
    Stalest refs per source per run. Default 400.

.PARAMETER AuctionBatch
    Stalest weapons for the heavy riven-auction sweep per run. Default 40.

.PARAMETER TaskName
    Scheduled Task name. Default "voidbroker-ingest".

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/install-schedule.ps1 -IntervalHours 6 -Batch 400
#>
param(
    [double]$IntervalHours = 6,
    [int]$Batch = 400,
    [int]$AuctionBatch = 40,
    [string]$TaskName = "voidbroker-ingest"
)

$ErrorActionPreference = "Stop"

# Repo root = parent of this script's directory.
$RepoRoot = Split-Path -Parent $PSScriptRoot

$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Error "uv not found on PATH. Install uv or run 'uv sync' first."
    exit 1
}
$uv = $uvCmd.Source

# Generate a wrapper .cmd so the task action has a fixed working directory and clean
# quoting, and so its console output (rich progress, any crash) is captured too. The app
# also logs structured stage lines to data\logs\voidbroker.log on its own.
$wrapper = Join-Path $PSScriptRoot "scheduled-ingest.cmd"
$wrapperBody = @"
@echo off
cd /d "$RepoRoot"
if not exist "data\logs" mkdir "data\logs"
"$uv" run voidbroker ingest --batch $Batch --auction-batch $AuctionBatch --orders --rivens --worldstate --details >> "data\logs\scheduled.log" 2>&1
"$uv" run voidbroker alert >> "data\logs\scheduled.log" 2>&1
"@
Set-Content -Path $wrapper -Value $wrapperBody -Encoding ascii

# schtasks needs the action quoted as a single token.
$tr = '"' + $wrapper + '"'

# Whole hours -> HOURLY; otherwise fall back to a minute cadence.
if ($IntervalHours -eq [math]::Floor($IntervalHours)) {
    $schedule = "HOURLY"; $modifier = [int]$IntervalHours
} else {
    $schedule = "MINUTE"; $modifier = [int][math]::Round($IntervalHours * 60)
}

Write-Host "Repo:     $RepoRoot"
Write-Host "Wrapper:  $wrapper"
Write-Host "Cadence:  every $IntervalHours h  (schtasks /SC $schedule /MO $modifier)"
Write-Host "Task:     $TaskName"
Write-Host ""

# /RL LIMITED + no /RU keeps it as the current interactive user: no elevation, no creds.
& schtasks.exe /Create /TN $TaskName /TR $tr /SC $schedule /MO $modifier /RL LIMITED /F
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Warning @"
schtasks could not register the task (exit $LASTEXITCODE).
This machine likely requires elevation to create scheduled tasks. Either:
  1. Re-run this script from an elevated PowerShell (Run as Administrator), or
  2. Open Task Scheduler -> Create Basic Task, trigger 'Daily/repeat every $IntervalHours h',
     action: Start a program -> $wrapper
The wrapper script above is ready either way; you can also just run it directly to ingest now:
  $wrapper
"@
    exit 1
}

Write-Host ""
Write-Host "Registered. Inspect:  schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Run once now:          schtasks /Run /TN $TaskName"
Write-Host "Logs:                  $RepoRoot\data\logs\ (voidbroker.log + scheduled.log)"
Write-Host "Health:                uv run voidbroker doctor"
