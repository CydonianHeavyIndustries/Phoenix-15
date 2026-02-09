@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PY=venv\Scripts\python.exe"
set "REQ=%~dp0requirements.txt"
set "REQS=%~dp0server\requirements.txt"
set "ENVFILE=%~dp0.env"
set "WIZARD=%~dp0setup_wizard.py"

echo Stopping any existing Bjorgsun-26 python instances...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process ^| Where-Object { ($_.Name -like 'python*') -and ($_.CommandLine -like '*Bjorgsun-26*') } ^| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

if not exist "%PY%" (
  echo [*] venv missing. Creating one and installing deps...
  py -3.11 -m venv "%~dp0venv" || (
    echo [!] Failed to create venv. Install Python 3.11 and retry.
    pause
    exit /b 1
  )
  "%PY%" -m pip install --upgrade pip setuptools wheel
  if exist "%REQ%" "%PY%" -m pip install -r "%REQ%"
  if exist "%REQS%" "%PY%" -m pip install -r "%REQS%"
)

echo [*] Checking audio dependencies...
"%PY%" -m pip show pycaw >nul 2>&1
if errorlevel 1 (
  echo [*] Installing pycaw/comtypes...
  "%PY%" -m pip install pycaw==20240210 comtypes==1.4.6
)

if not exist "%ENVFILE%" if exist "%WIZARD%" (
  echo [*] No .env found. Launching setup wizard...
  "%PY%" "%WIZARD%"
)

echo.
echo ==========================
echo   Bjorgsun launcher (bat)
echo ==========================
echo 1^) Stable UI
echo 2^) Dev UI
echo 3^) Debug (login only, type /wake to start)
echo 4^) Sleep (failsafe)
echo 5^) Quit
echo.
set /p CH=Select option [1-5]: 

if "%CH%"=="1" (
  set "UI_DEV_MODE="
  set "BJORGSUN_FORCE="
  set "BJORGSUN_REQUIRE_WAKE=1"
  "%PY%" "%~dp0launcher_bjorgsun.py"
  goto :eof
)
if "%CH%"=="2" (
  set "UI_DEV_MODE=1"
  set "BJORGSUN_FORCE="
  set "BJORGSUN_REQUIRE_WAKE=1"
  "%PY%" "%~dp0launcher_bjorgsun.py"
  goto :eof
)
if "%CH%"=="3" (
  set "UI_DEV_MODE="
  set "BJORGSUN_FORCE="
  set "BJORGSUN_SKIP_LOGIN=0"
  set "BJORGSUN_REQUIRE_WAKE=1"
  "%PY%" "%~dp0launcher_bjorgsun.py"
  goto :eof
)
if "%CH%"=="4" (
  if exist "%~dp0Gotosleep.bat" (
    call "%~dp0Gotosleep.bat"
  ) else (
    echo [!] Gotosleep.bat not found.
    pause
  )
  goto :eof
)

if "%CH%"=="5" (
  echo Bye.
  endlocal
  goto :eof
)

echo Bye.
endlocal
