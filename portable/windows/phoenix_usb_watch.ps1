param(
  [int]$IntervalSec = 2
)

$ErrorActionPreference = "SilentlyContinue"
$logDir = Join-Path $env:LOCALAPPDATA "Phoenix-15\logs"
$logFile = Join-Path $logDir "usb_autorun.log"

function Write-Log {
  param([string]$Message)
  try {
    if (-not (Test-Path $logDir)) {
      New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
    $ts = (Get-Date).ToString("s")
    Add-Content -Path $logFile -Value "[$ts] $Message"
  } catch {}
}

function Test-Port {
  param([int]$Port)
  $client = $null
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(200)
    if ($ok -and $client.Connected) {
      return $true
    }
  } catch {}
  finally {
    try { if ($client) { $client.Close() } } catch {}
  }
  return $false
}

function Find-PhoenixLauncher {
  $systemDrive = ($env:SystemDrive -replace "\\", "").ToUpper()
  try {
    $drives = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -in 2, 3 }
  } catch {
    $drives = @()
  }
  foreach ($drive in $drives) {
    try {
      $driveId = ($drive.DeviceID -replace "\\", "").ToUpper()
      if ($driveId -eq $systemDrive) { continue }
      $candidate = Join-Path $drive.DeviceID "Bjorgsun-26\portable\windows\run_phoenix.bat"
      if (Test-Path $candidate) {
        return $candidate
      }
    } catch {}
  }
  return $null
}

Write-Log "watcher_start"
while ($true) {
  try {
    if (-not (Test-Port 1326)) {
      $launcher = Find-PhoenixLauncher
      if ($launcher) {
        Write-Log "launcher_found $launcher"
        Start-Process -FilePath $launcher -WorkingDirectory (Split-Path $launcher -Parent)
        Start-Sleep -Seconds 10
      }
    }
  } catch {
    Write-Log "watcher_error $($_.Exception.Message)"
  }
  Start-Sleep -Seconds $IntervalSec
}
