@echo off
setlocal
rem Helper script to run the new Figma-derived UI in dev mode (Vite).
set "PATH=C:\Program Files\nodejs;%PATH%"
cd /d "%~dp0"
echo Starting Vite dev server...
npm run dev
endlocal
