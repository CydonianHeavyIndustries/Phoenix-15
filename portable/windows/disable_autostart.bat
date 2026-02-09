@echo off
setlocal EnableExtensions
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0disable_autostart.ps1"
endlocal
