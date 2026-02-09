param(
    [string]$Root = "",
    [string]$DevRepo = "",
    [string]$AltRoot = ""
)

$scriptRoot = Resolve-Path $PSScriptRoot
if (-not $Root) {
    $Root = Resolve-Path (Join-Path $scriptRoot "..")
}
if (-not $DevRepo) {
    $DevRepo = $Root
}
if (-not $AltRoot) {
    $AltRoot = $env:BJORG_ALT_ROOT
}

Write-Host "[Launcher] Root: $Root"
Write-Host "[Launcher] Dev repo: $DevRepo"

function Load-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Write-Host "[ENV] loading $Path"
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line) { return }
        if ($line.StartsWith("#")) { return }
        $pair = $line -split "=", 2
        if ($pair.Count -lt 2) { return }
        $key = $pair[0].Trim()
        $value = $pair[1]
        if (-not $key) { return }
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

$envFiles = @(
    (Join-Path $Root ".env"),
    (Join-Path $DevRepo ".env")
)
if ($AltRoot) {
    $envFiles += (Join-Path $AltRoot ".env")
}
if ($env:BJORG_ENV_ADDITIONAL) {
    $extras = $env:BJORG_ENV_ADDITIONAL -split ";"
    $envFiles += $extras
}
$envFiles | Sort-Object -Unique | ForEach-Object { Load-EnvFile $_ }
[Environment]::SetEnvironmentVariable("BJORG_STABLE_ROOT", $Root, "Process")

function Launch-Service {
    param(
        [string]$Label,
        [string]$Exe,
        [string[]]$Args,
        [string]$WorkingDirectory,
        [switch]$ShowWindow
    )
    if (-not (Test-Path $Exe)) {
        Write-Warning "$Label skipped (missing $Exe)"
        return
    }
    if (-not (Test-Path $WorkingDirectory)) {
        Write-Warning "$Label skipped (missing $WorkingDirectory)"
        return
    }
    $style = $ShowWindow.IsPresent ? 'Normal' : 'Hidden'
    try {
        Start-Process -FilePath $Exe -ArgumentList $Args -WorkingDirectory $WorkingDirectory -WindowStyle $style | Out-Null
        Write-Host "[$Label] launched ($style)."
    } catch {
        Write-Warning "$Label failed: $_"
    }
}

$venv = Join-Path $Root "venv\Scripts\python.exe"
$serverDir = Join-Path $Root "server"

Launch-Service -Label "Local API" -Exe $venv -Args @("server.py") -WorkingDirectory $serverDir
Launch-Service -Label "Voice Daemon" -Exe $venv -Args @("voice_daemon.py") -WorkingDirectory $serverDir
Launch-Service -Label "UI / HUD" -Exe $venv -Args @("scripts\start_ui.py") -WorkingDirectory $Root -ShowWindow
Launch-Service -Label "Discord Bridge" -Exe $venv -Args @("systems\discord_bridge.py") -WorkingDirectory $Root
Launch-Service -Label "Tablet Agent" -Exe $venv -Args @("systems\tablet_ops.py") -WorkingDirectory $Root

$ngrok = $null
try {
    $ng = Get-Command ngrok -ErrorAction Stop
    $ngrok = $ng.Source
} catch {
    Write-Warning "ngrok not found on PATH."
}
if ($ngrok) {
    Launch-Service -Label "ngrok 1326" -Exe $ngrok -Args @("http", "1326") -WorkingDirectory $Root
}

Write-Host "[Launcher] All services triggered. UI should appear momentarily."
