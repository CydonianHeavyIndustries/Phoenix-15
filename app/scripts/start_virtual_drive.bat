@echo off
setlocal
set PSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe
set SCRIPT=%~dp0mount_virtual_drive.ps1
%PSHELL% -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -DriveLetter B
endlocal
