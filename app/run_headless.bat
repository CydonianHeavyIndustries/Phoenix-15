@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ---------------------------------------------------------------------------
rem Bjorgsun-26 headless launcher (backend + UI, LAN accessible)
rem - Serves backend on 0.0.0.0:1326 (server.py default)
rem - Serves UI on 0.0.0.0:56795 (override via BJORGSUN_UI_PORT)
rem - Runs in background (no browser/webview)
rem ---------------------------------------------------------------------------

set "ROOT=%~dp0"
set "LOGDIR=%ROOT%logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "TS=%date:~-4%%date:~4,2%%date:~7,2%_%time: =0%"
set "TS=%TS::=%"
set "TS=%TS:.=%"
set "LOGFILE=%LOGDIR%\\headless_%TS%.log"

set "PYTHON=%ROOT%venv\\Scripts\\python.exe"
if not exist "%PYTHON%" (
  echo [%date% %time%] ERROR: venv python not found at %PYTHON% >> "%LOGFILE%"
  exit /b 1
)

rem Ensure Node is on PATH for UI build if needed
set "NODE_PATH=C:\\Program Files\\nodejs"
set "PATH=%NODE_PATH%;%PATH%"

rem Ollama defaults
set "OLLAMA_DIR=%LOCALAPPDATA%\\Programs\\Ollama"
if not exist "%OLLAMA_DIR%\\ollama.exe" if exist "%ProgramFiles%\\Ollama\\ollama.exe" set "OLLAMA_DIR=%ProgramFiles%\\Ollama"
set "PATH=%OLLAMA_DIR%;%PATH%"
if exist "%USERPROFILE%\\.ollama\\models" set "OLLAMA_MODELS=%USERPROFILE%\\.ollama\\models"
if "%OLLAMA_MODEL%"=="" set "OLLAMA_MODEL=qwen2.5:7b"

echo [%date% %time%] Headless launcher starting... > "%LOGFILE%"

rem Start Ollama serve if needed
curl -s http://127.0.0.1:11434/api/tags >nul 2>nul
if errorlevel 1 (
  echo [%date% %time%] Starting Ollama service... >> "%LOGFILE%"
  start "" /b "%OLLAMA_DIR%\\ollama.exe" serve
  timeout /t 3 >nul
)

rem Ensure selected model is present
ollama list | find /i "%OLLAMA_MODEL%" >nul 2>nul
if errorlevel 1 (
  echo [%date% %time%] Pulling %OLLAMA_MODEL%... >> "%LOGFILE%"
  ollama pull %OLLAMA_MODEL% >> "%LOGFILE%" 2>&1
)

rem Launch backend
echo [%date% %time%] Starting backend (server.py)... >> "%LOGFILE%"
start "" /b "%PYTHON%" "%ROOT%server\\server.py"

rem Launch UI headless, bind to 0.0.0.0 so LAN works
set "BJORGSUN_UI_HOST=0.0.0.0"
set "BJORGSUN_UI_WEBVIEW=0"
set "BJORGSUN_UI_HEADLESS=1"
set "BJORGSUN_UI_PORT=56795"
set "BJORGSUN_UI_STDLOG=%LOGDIR%\\start_ui_stdout_%TS%.log"
set "BJORGSUN_UI_CRASHLOG=%LOGDIR%\\ui_crash_%TS%.log"
set "BJORGSUN_UI_DIST=%ROOT%ui\\scifiaihud\\build"
set "BJORGSUN_USER=Father"
set "BJORGSUN_PASS="

rem Build UI bundle if missing
if not exist "%BJORGSUN_UI_DIST%\\index.html" (
  echo [%date% %time%] UI build missing, building... >> "%LOGFILE%"
  pushd "%ROOT%ui\\scifiaihud"
  if not exist node_modules (
    call npm install >> "%LOGFILE%" 2>&1
  )
  call npm run build >> "%LOGFILE%" 2>&1
  popd
)

echo [%date% %time%] Starting UI (headless)... >> "%LOGFILE%"
start "" /b "%PYTHON%" "%ROOT%scripts\\start_ui.py"

echo [%date% %time%] Headless launcher done (processes running in background). >> "%LOGFILE%"
endlocal
