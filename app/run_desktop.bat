@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%audio_profile_app\frontend"
set "ELECTRON_EXE=%APP_DIR%\node_modules\electron\dist\electron.exe"
set "ELECTRON_RUN_AS_NODE="
set "PYTHONUTF8=1"

if not exist "%APP_DIR%" (
  echo Audio profile app folder not found: %APP_DIR%
  exit /b 1
)

if not exist "%ELECTRON_EXE%" (
  echo Installing desktop app dependencies...
  pushd "%APP_DIR%"
  call npm.cmd install
  popd
)

set "BJORGSUN_PY=%ROOT%venv\Scripts\python.exe"

pushd "%APP_DIR%"
"%ELECTRON_EXE%" .
popd
endlocal
