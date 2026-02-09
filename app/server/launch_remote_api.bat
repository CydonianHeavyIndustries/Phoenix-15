@echo off
setlocal

cd /d %~dp0

if not exist ".venv" (
    py -3.11 -m venv .venv
)

start "Bjorgsun-26 Server" cmd /k "call .venv\Scripts\activate.bat && pip install --upgrade pip >nul && pip install -r requirements.txt && python server.py"

timeout /t 3 >nul

start "ngrok 1326" cmd /k "ngrok http 1326"

echo Remote API stack launched. Close these windows to stop the services.
endlocal
