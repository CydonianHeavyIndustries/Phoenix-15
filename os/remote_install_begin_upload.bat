@echo off
setlocal EnableExtensions
title Phoenix-15 Remote Upload Trigger

set "TRIGGER_FILE=%~dp0remote_upload_begin.flag"

echo [phoenix] Sending begin-upload trigger...
echo %date% %time% > "%TRIGGER_FILE%"
if errorlevel 1 (
  echo [ERROR] Could not write trigger file:
  echo %TRIGGER_FILE%
  pause
  exit /b 1
)

echo [phoenix] Trigger sent.
echo [phoenix] If the installer window is open, it should continue now.
pause
exit /b 0
