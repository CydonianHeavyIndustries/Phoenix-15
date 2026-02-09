@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "PY=%ROOT%venv\Scripts\python.exe"
set "PYW=%ROOT%venv\Scripts\pythonw.exe"
set "LOG=%ROOT%logs\tray_launch.log"

if not exist "%ROOT%logs" mkdir "%ROOT%logs"

echo [%date% %time%] Closing previous instances... >> "%LOG%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\\stop_existing_instances.ps1" >> "%LOG%" 2>&1

if not exist "%PY%" (
  echo [%date% %time%] venv python not found at %PY% >> "%LOG%"
  echo venv python not found. Please set up the venv and retry.
  exit /b 1
)

echo [%date% %time%] Ensuring tray dependencies... >> "%LOG%"
echo Installing tray dependencies (first run only)...
"%PY%" -m pip show pystray >nul 2>&1
if errorlevel 1 (
  "%PY%" -m pip install --quiet pystray pillow pywebview >> "%LOG%" 2>&1
)

set "LAUNCHER=%PY%"
if exist "%PYW%" set "LAUNCHER=%PYW%"

echo [%date% %time%] Starting tray controller with %LAUNCHER% >> "%LOG%"
start "" /D "%ROOT%" "%LAUNCHER%" "%ROOT%tray_control.py"

REM If tray controller failed to start, fall back to direct launch
powershell -NoProfile -Command "Start-Sleep -Seconds 2; $ok=$false; try { $p=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*tray_control.py*' -and $_.Name -like 'python*' }; if ($p) { $ok=$true } } catch {}; if (-not $ok) { $log='%ROOT%logs\\tray_control.log'; if (Test-Path $log) { $age=(Get-Date)-(Get-Item $log).LastWriteTime; if ($age.TotalSeconds -lt 15) { $ok=$true } } }; if (-not $ok) { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo [%date% %time%] tray_control missing; falling back to launch_phoenix.bat >> "%LOG%"
  call "%ROOT%launch_phoenix.bat"
)

endlocal
