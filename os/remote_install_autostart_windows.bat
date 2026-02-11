@echo off
setlocal EnableExtensions
title Phoenix-15 Auto Remote Installer

set "BASE=%~dp0"
set "DISCOVERY_PS=%BASE%discover_phoenix_target.ps1"

if not exist "%DISCOVERY_PS%" (
  echo [ERROR] Missing discovery script:
  echo %DISCOVERY_PS%
  pause
  exit /b 1
)

echo ============================================================
echo         Phoenix-15 Auto Remote Installer (Windows)
echo ============================================================
echo.
echo This script auto-discovers a ready Ubuntu target that is
echo running the Phoenix readiness beacon on port 16326.
echo.
echo On Ubuntu, run:
echo   bash /media/ubuntu/BOO1/remote_install_target_ready_ubuntu.sh
echo.
echo Searching network for target...

set "FOUND_HOST="
set "FOUND_USER="

for /f "usebackq tokens=1,2 delims=|" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%DISCOVERY_PS%"`) do (
  set "FOUND_HOST=%%A"
  set "FOUND_USER=%%B"
)

if "%FOUND_HOST%"=="" (
  echo [ERROR] No ready Phoenix target discovered on LAN.
  echo Ensure Ubuntu beacon script is running and retry.
  pause
  exit /b 1
)

if "%FOUND_USER%"=="" set "FOUND_USER=ubuntu"

echo [OK] Found target: %FOUND_HOST% (user: %FOUND_USER%)
echo.
set "PHX_TARGET_HOST=%FOUND_HOST%"
set "PHX_TARGET_USER=%FOUND_USER%"
set "PHX_REPO_URL=https://github.com/CydonianHeavyIndustries/Phoenix-15.git"
set "PHX_BRANCH=main"
set "PHX_TARGET_DIR=~/Phoenix-15"

call "%BASE%remote_install_phoenix_os.bat" --now
exit /b %ERRORLEVEL%
