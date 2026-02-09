param()

$taskName = "Phoenix-15 USB AutoStart"
$destRoot = Join-Path $env:LOCALAPPDATA "Phoenix-15\autostart"
$destScript = Join-Path $destRoot "phoenix_usb_watch.ps1"

try {
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false | Out-Null
} catch {
  schtasks /Delete /TN "$taskName" /F | Out-Null
}

try {
  if (Test-Path $destScript) {
    Remove-Item -Path $destScript -Force
  }
} catch {}

Write-Host "Phoenix-15 autostart disabled."
