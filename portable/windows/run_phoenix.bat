@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..\\..") do set "ROOT=%%~fI"
set "APP=%ROOT%\\app"
set "PY=%APP%\\venv\\Scripts\\python.exe"
set "PORTABLE_PY=%ROOT%\\portable\\runtime\\python\\python.exe"

if not exist "%APP%\\scripts\\portable_launcher.py" (
  echo Portable launcher missing at %APP%\\scripts\\portable_launcher.py
  exit /b 1
)

if not exist "%PY%" (
  if exist "%PORTABLE_PY%" (
    set "PY=%PORTABLE_PY%"
  ) else (
    echo Python venv not found.
    echo Run portable\\windows\\setup_venv.bat or install Python 3.11+.
    exit /b 1
  )
)

pushd "%APP%"
"%PY%" "%APP%\\scripts\\portable_launcher.py"
popd
endlocal
