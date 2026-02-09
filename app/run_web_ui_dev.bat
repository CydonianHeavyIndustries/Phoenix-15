@echo off
setlocal
rem Dev workflow: start Vite and open the app with dev UI URL.
set "PATH=C:\Program Files\nodejs;%PATH%"
cd /d "%~dp0"

rem Start Vite dev server in a new window
start "UI Dev Server" cmd /k "cd ui && set PATH=C:\Program Files\nodejs;%PATH% && npm run dev"

rem Point launcher to the dev server
set BJORGSUN_UI_DEV=1
set BJORGSUN_UI_DEV_URL=http://127.0.0.1:5173/

echo Starting Bjorgsun web UI (dev mode)...
python scripts\\start_ui.py
endlocal
