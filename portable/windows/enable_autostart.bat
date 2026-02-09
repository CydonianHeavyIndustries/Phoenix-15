jus@echo off
setlocal EnableExtensions
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0enable_autostart.ps1"
endlocal
