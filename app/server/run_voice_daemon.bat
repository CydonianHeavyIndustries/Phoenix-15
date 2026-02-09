@echo off
setlocal

cd /d %~dp0

if not exist ".venv" (
    py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat

echo Starting Bjorgsun Voice Daemon (manual test mode)...
python voice_daemon.py

endlocal
