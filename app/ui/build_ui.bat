@echo off
setlocal
rem Build the production bundle for the new UI (outputs to build/).
set "PATH=C:\Program Files\nodejs;%PATH%"
cd /d "%~dp0"
echo Building UI...
npm run build
endlocal
