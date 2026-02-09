@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "ROOT=%~dp0"
set "NODE_PATH=C:\Program Files\nodejs"
set "PATH=%NODE_PATH%;%PATH%"
set "LOGDIR=%ROOT%logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmssfff"') do set "TS=%%I"
set "UI_LOG=%LOGDIR%\\start_ui_stdout_%TS%.log"
set "CRASH_LOG=%LOGDIR%\\ui_crash_%TS%.log"
set "SERVER_LOG=%LOGDIR%\\server_stdout_%TS%.log"
echo [%DATE% %TIME%] --- run_web_ui.bat start --- > "%UI_LOG%"
echo [%DATE% %TIME%] --- run_web_ui.bat start --- > "%CRASH_LOG%"
echo [%DATE% %TIME%] --- server log start --- > "%SERVER_LOG%"

rem Use project venv python
set "PYTHON=%ROOT%venv\\Scripts\\python.exe"
if not exist "%PYTHON%" (
  echo venv python not found at %PYTHON%
  pause
  exit /b 1
)
set "PYTHONPATH=%ROOT%"

echo Checking for running Bjorgsun-26 python instances...
echo [%DATE% %TIME%] checking other processes >> "%UI_LOG%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*') -and ($_.CommandLine -like '*Bjorgsun-26*') -and ($_.ProcessId -ne $PID) -and ($_.CommandLine -notlike '*run_web_ui.bat*') } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }" >nul 2>&1
echo [%DATE% %TIME%] finished process cleanup >> "%UI_LOG%"

cd /d "%ROOT%"

echo Building Sci-Fi HUD UI bundle...
echo [%DATE% %TIME%] building scifiaihud >> "%UI_LOG%"
pushd ui\\scifiaihud
if not exist node_modules (
  call npm install
)
call npm run build
if errorlevel 1 (
  echo Sci-Fi HUD build failed.
  echo [%DATE% %TIME%] scifiaihud build failed >> "%UI_LOG%"
  pause
  popd
  exit /b 1
)
popd
echo [%DATE% %TIME%] scifiaihud build ok >> "%UI_LOG%"

echo.
echo Starting FastAPI backend...
REM Start backend in background (no extra window) and capture logs
pushd "%ROOT%"
powershell -NoProfile -Command "Start-Process -FilePath '%PYTHON%' -ArgumentList '%ROOT%server\\server.py' -WorkingDirectory '%ROOT%' -WindowStyle Hidden -RedirectStandardOutput '%SERVER_LOG%' -RedirectStandardError '%SERVER_LOG%'"
popd
timeout /t 2 >nul
rem confirm backend is reachable
powershell -NoProfile -Command "for($i=0;$i -lt 20;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:1326/ping | Out-Null; exit 0}catch{Start-Sleep -Milliseconds 500}} exit 1" >nul 2>&1
if errorlevel 1 (
  echo [%DATE% %TIME%] backend ping failed >> "%UI_LOG%"
  echo [backend log] >> "%UI_LOG%"
  type "%SERVER_LOG%" >> "%UI_LOG%"
)
echo [%DATE% %TIME%] backend start attempted >> "%UI_LOG%"

REM Prefer native window if available; fall back to browser if webview missing
set BJORGSUN_UI_WEBVIEW=1
set BJORGSUN_UI_WEBVIEW_ENGINE=edgechromium
set BJORGSUN_UI_DEV=0
set BJORGSUN_UI_BUILD_VERSION=%DATE%_%TIME%
set BJORGSUN_UI_PORT=56795
set BJORGSUN_USER=Father
set BJORGSUN_PASS=
REM Use the built Sci-Fi HUD bundle (Vite outputs to build/)
set BJORGSUN_UI_DIST=%ROOT%ui\\scifiaihud\\build

set BJORGSUN_UI_STDLOG=%UI_LOG%
set BJORGSUN_UI_CRASHLOG=%CRASH_LOG%
echo Ensuring webview dependency...
"%PYTHON%" -m pip install --quiet pywebview >> "%UI_LOG%" 2>&1
echo Starting Bjorgsun UI (native window if available)...
echo [log] Writing UI stdout/stderr to %UI_LOG%
"%PYTHON%" scripts\\start_ui.py
set "PY_ERR=%ERRORLEVEL%"
echo [%DATE% %TIME%] start_ui.py exited code %PY_ERR% >> "%UI_LOG%"
if not "%PY_ERR%"=="0" (
  echo [%DATE% %TIME%] start_ui.py exit %PY_ERR% >> "%CRASH_LOG%"
  echo [begin ui_stdout tail] >> "%CRASH_LOG%"
  type "%UI_LOG%" >> "%CRASH_LOG%"
  echo [end ui_stdout tail] >> "%CRASH_LOG%"
)

echo UI exited.
pause
endlocal
