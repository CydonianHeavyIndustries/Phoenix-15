@echo off
setlocal EnableExtensions

rem Unified launcher: server + UI headless, binds to 0.0.0.0 for LAN.

set "ROOT=%~dp0"
set "PY=%ROOT%venv\\Scripts\\python.exe"
set "LOGDIR=%ROOT%logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "TS=%date:~-4%%date:~4,2%%date:~7,2%_%time: =0%"
set "TS=%TS::=%"
set "TS=%TS:.=%"
set "MAINLOG=%LOGDIR%\\stack_%TS%.log"

if not exist "%PY%" (
  echo [%date% %time%] venv python not found at %PY% >> "%MAINLOG%"
  echo venv python not found. Please set up the venv and retry.
  exit /b 1
)

echo [%date% %time%] Checking audio dependencies... >> "%MAINLOG%"
"%PY%" -m pip show pycaw >nul 2>nul
if errorlevel 1 (
  echo [%date% %time%] Installing pycaw/comtypes... >> "%MAINLOG%"
  "%PY%" -m pip install pycaw==20240210 comtypes==1.4.6 >> "%MAINLOG%" 2>&1
)

rem Ollama setup
set "OLLAMA_DIR=%LOCALAPPDATA%\\Programs\\Ollama"
if not exist "%OLLAMA_DIR%\\ollama.exe" if exist "%ProgramFiles%\\Ollama\\ollama.exe" set "OLLAMA_DIR=%ProgramFiles%\\Ollama"
set "PATH=%OLLAMA_DIR%;%PATH%"
if exist "%USERPROFILE%\\.ollama\\models" set "OLLAMA_MODELS=%USERPROFILE%\\.ollama\\models"
if "%OLLAMA_MODEL%"=="" set "OLLAMA_MODEL=qwen2.5:7b"

rem Node path for UI build
set "NODE_PATH=C:\\Program Files\\nodejs"
set "PATH=%NODE_PATH%;%PATH%"

echo [%date% %time%] Starting stack... > "%MAINLOG%"

rem Start Ollama service if not already running
curl -s http://127.0.0.1:11434/api/tags >nul 2>nul
if errorlevel 1 (
  echo [%date% %time%] Starting Ollama service... >> "%MAINLOG%"
  start "" /b "%OLLAMA_DIR%\\ollama.exe" serve
  timeout /t 3 >nul
)

rem Ensure selected model is present
ollama list | find /i "%OLLAMA_MODEL%" >nul 2>nul
if errorlevel 1 (
  echo [%date% %time%] Pulling %OLLAMA_MODEL%... >> "%MAINLOG%"
  ollama pull %OLLAMA_MODEL% >> "%MAINLOG%" 2>&1
)

rem Start backend
echo [%date% %time%] Starting backend... >> "%MAINLOG%"
start "" /b "%PY%" "%ROOT%server\\server.py"

rem Build UI if missing
set "UI_BUILD=%ROOT%ui\\scifiaihud\\build"
if not exist "%UI_BUILD%\\index.html" (
  echo [%date% %time%] UI build missing; building... >> "%MAINLOG%"
  pushd "%ROOT%ui\\scifiaihud"
  if not exist node_modules (
    call npm install >> "%MAINLOG%" 2>&1
  )
  call npm run build >> "%MAINLOG%" 2>&1
  popd
)

rem Launch UI headless, bind 0.0.0.0
set "BJORGSUN_UI_HOST=0.0.0.0"
set "BJORGSUN_UI_PORT=56795"
set "BJORGSUN_UI_WEBVIEW=0"
set "BJORGSUN_UI_HEADLESS=1"
set "BJORGSUN_UI_DIST=%UI_BUILD%"
set "BJORGSUN_UI_STDLOG=%LOGDIR%\\start_ui_stdout_%TS%.log"
set "BJORGSUN_UI_CRASHLOG=%LOGDIR%\\ui_crash_%TS%.log"
set "BJORGSUN_USER=Father"
set "BJORGSUN_PASS="

echo [%date% %time%] Starting UI... >> "%MAINLOG%"
start "" /b "%PY%" "%ROOT%scripts\\start_ui.py"

echo [%date% %time%] Stack launched (backend+UI). Logs: %MAINLOG% >> "%MAINLOG%"
endlocal
