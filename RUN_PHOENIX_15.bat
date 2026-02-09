@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
if exist "%ROOT%portable\windows\run_phoenix.bat" (
  call "%ROOT%portable\windows\run_phoenix.bat"
  exit /b %errorlevel%
)

if exist "%ROOT%app\launch_phoenix.bat" (
  call "%ROOT%app\launch_phoenix.bat"
  exit /b %errorlevel%
)

echo Phoenix-15 launcher not found.
pause
endlocal
