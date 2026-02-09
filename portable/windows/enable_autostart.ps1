param()

$taskName = "Phoenix-15 USB AutoStart"
$srcScript = Join-Path $PSScriptRoot "phoenix_usb_watch.ps1"
$destRoot = Join-Path $env:LOCALAPPDATA "Phoenix-15\autostart"
$destScript = Join-Path $destRoot "phoenix_usb_watch.ps1"

if (-not (Test-Path $srcScript)) {
  Write-Host "Missing watcher script: $srcScript"
  exit 1
}

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null
Copy-Item -Path $srcScript -Destination $destScript -Force

try {
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$destScript`""
  $trigger = New-ScheduledTaskTrigger -AtLogOn
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 0) -Hidden
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
} catch {
  schtasks /Create /TN "$taskName" /SC ONLOGON /RL LIMITED /TR "powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$destScript`"" /F | Out-Null
}

Start-Process -FilePath "powershell.exe" -ArgumentList "-NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$destScript`""
Write-Host "Phoenix-15 autostart enabled."
