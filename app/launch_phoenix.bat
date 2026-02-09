@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "LOGDIR=%ROOT%logs"
set "LOGFILE=%LOGDIR%\\launch_phoenix.log"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM Paths for Ollama (default install locations)
set "OLLAMA_DIR=%LOCALAPPDATA%\Programs\Ollama"
if not exist "%OLLAMA_DIR%\\ollama.exe" if exist "%ProgramFiles%\\Ollama\\ollama.exe" set "OLLAMA_DIR=%ProgramFiles%\\Ollama"
set "PATH=%OLLAMA_DIR%;%PATH%"
rem Use local Ollama model store
if exist "%USERPROFILE%\\.ollama\\models" set "OLLAMA_MODELS=%USERPROFILE%\\.ollama\\models"

echo [Phoenix-15] Starting launcher... > "%LOGFILE%"
echo [Phoenix-15] Preparing environment...
echo [Phoenix-15] Starting launcher...

echo [Phoenix-15] Closing previous instances...
echo [Phoenix-15] Closing previous instances... >> "%LOGFILE%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\\stop_existing_instances.ps1" >> "%LOGFILE%" 2>&1

REM Prompt for tablet IP only when explicitly enabled (avoids blocking tray launch)
if "%PHOENIX_REMOTE_BASE%"=="" (
  if /I "%PHOENIX_PROMPT_REMOTE%"=="1" (
    set /p TBLIP=Enter tablet IP for Phoenix state (blank for local PC only): 
    if not "%TBLIP%"=="" (
      set "PHOENIX_REMOTE_BASE=http://%TBLIP%:8788"
    )
  )
)

if "%OLLAMA_ENDPOINT%"=="" set "OLLAMA_ENDPOINT=http://127.0.0.1:11434"
if "%OLLAMA_MODEL%"=="" set "OLLAMA_MODEL=qwen2.5:7b"

REM Start Ollama daemon if not listening
curl -s http://127.0.0.1:11434/api/tags >nul 2>nul
if errorlevel 1 (
  echo [Phoenix-15] Starting Ollama service...
  echo [Phoenix-15] Starting Ollama service... >> "%LOGFILE%"
  start "" /b "%OLLAMA_DIR%\\ollama.exe" serve
  timeout /t 3 >nul
)

REM Ensure selected model is available
ollama list | find /i "%OLLAMA_MODEL%" >nul 2>nul
if errorlevel 1 (
  echo [Phoenix-15] Pulling model %OLLAMA_MODEL%...
  echo [Phoenix-15] Pulling model %OLLAMA_MODEL%... >> "%LOGFILE%"
  ollama pull %OLLAMA_MODEL%
)

REM Verify python
if not exist "%ROOT%venv\\Scripts\\python.exe" (
  echo [Phoenix-15] ERROR: venv Python not found at %ROOT%venv\Scripts\python.exe
  echo [Phoenix-15] ERROR: venv Python not found at %ROOT%venv\Scripts\python.exe >> "%LOGFILE%"
  pause
  exit /b 1
)

cd /d "%ROOT%"
echo [Phoenix-15] Checking audio dependencies...
echo [Phoenix-15] Checking audio dependencies... >> "%LOGFILE%"
"%ROOT%venv\\Scripts\\python.exe" -m pip show pycaw >nul 2>nul
if errorlevel 1 (
  echo [Phoenix-15] Installing pycaw/comtypes...
  echo [Phoenix-15] Installing pycaw/comtypes... >> "%LOGFILE%"
  "%ROOT%venv\\Scripts\\python.exe" -m pip install pycaw==20240210 comtypes==1.4.6 >> "%LOGFILE%" 2>&1
)
echo [Phoenix-15] Starting backend server...
echo [Phoenix-15] Starting backend server... >> "%LOGFILE%"
start "" /b ".\\venv\\Scripts\\python.exe" server\\server.py

echo [Phoenix-15] Launching UI...
echo [Phoenix-15] Launching UI... >> "%LOGFILE%"
call ".\\run_web_ui.bat"

echo [Phoenix-15] Done.
echo [Phoenix-15] Done. >> "%LOGFILE%"
pause

endlocal
