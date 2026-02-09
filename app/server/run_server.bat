@echo off
setlocal

cd /d %~dp0

if not exist ".venv" (
    echo Creating virtual environment...
    py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing/updating dependencies...
pip install --upgrade pip >nul
pip install -r requirements.txt

echo Starting Bjorgsun-26 server on port 1326...
python server.py

endlocal
