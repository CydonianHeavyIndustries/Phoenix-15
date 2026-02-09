param(
  [int]$ExcludePid = 0,
  [string]$Match = "Bjorgsun-26"
)

$matchText = if ($Match) { "*$Match*" } else { "*Bjorgsun-26*" }
$currentPid = $ExcludePid

Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and
    $_.CommandLine -like $matchText -and
    $_.ProcessId -ne $currentPid -and
    $_.CommandLine -notlike "*run_tray.bat*" -and
    $_.CommandLine -notlike "*stop_existing_instances.ps1*" -and
    (
      $_.Name -like "python*" -or
      $_.Name -like "node*" -or
      $_.Name -like "Bjorgsun-26*" -or
      $_.Name -like "Phoenix-15*"
    )
  } |
  ForEach-Object {
    try {
      Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
    } catch {
    }
  }
