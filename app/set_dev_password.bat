@echo off
setlocal
cd /d "%~dp0"

set "ENVFILE=%~dp0.env"
if not exist "%ENVFILE%" (
  echo [!] .env not found in %~dp0. Please run this from the project root.
  pause
  exit /b 1
)

set /p DEV_PWD=Enter DEV_MODE_PASSWORD (overwrite existing): 
if "%DEV_PWD%"=="" (
  echo [!] No password entered. Aborting.
  pause
  exit /b 1
)

copy "%ENVFILE%" "%ENVFILE%.bak" >nul
findstr /v /r "^DEV_MODE_PASSWORD=" "%ENVFILE%" > "%ENVFILE%.tmp"
echo DEV_MODE_PASSWORD=%DEV_PWD%>>"%ENVFILE%.tmp"
move /y "%ENVFILE%.tmp" "%ENVFILE%" >nul

echo [✓] DEV_MODE_PASSWORD updated. Backup saved at %ENVFILE%.bak
pause
endlocal
