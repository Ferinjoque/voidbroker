<#
.SYNOPSIS
    Remove the voidbroker ingest Scheduled Task registered by install-schedule.ps1.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/uninstall-schedule.ps1
#>
param(
    [string]$TaskName = "voidbroker-ingest"
)

# Use schtasks (matches how install registers it, and works without elevation).
& schtasks.exe /Query /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "No task named '$TaskName' found. Nothing to do."
    exit 0
}

& schtasks.exe /Delete /TN $TaskName /F
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removed Scheduled Task '$TaskName'. The archive is untouched."
} else {
    Write-Warning "Could not delete '$TaskName' (exit $LASTEXITCODE). Try an elevated terminal."
}
