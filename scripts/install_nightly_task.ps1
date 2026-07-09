# Register a Windows Scheduled Task to run update_and_push.ps1 every night at 3:00 AM.
# Run this script once as Administrator (or it will prompt).

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $RepoRoot "scripts\update_and_push.ps1"
$TaskName = "MCStatsDashboardNightly"

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""

$Trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Description "Regenerate Minecraft server stats dashboard and push to GitHub" `
    -Force

Write-Host "Scheduled task '$TaskName' installed - runs daily at 3:00 AM."
Write-Host "Test now with: Start-ScheduledTask -TaskName $TaskName"
