@echo off
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0..\\..") do set "ROOT=%%~fI"
set "APP=%ROOT%\\app"
set "PYBASE=%ROOT%\\portable\\runtime\\python\\python.exe"
set "PY=%APP%\\venv\\Scripts\\python.exe"

if not exist "%PYBASE%" (
  echo Portable Python not found at %PYBASE%.
  echo Install Python 3.11+ or place the embeddable runtime at portable\\runtime\\python\\python.exe.
  exit /b 1
)

if exist "%APP%\\venv" (
  echo venv already exists at %APP%\\venv
  exit /b 0
)

pushd "%APP%"
"%PYBASE%" -m venv "%APP%\\venv"
set "PY=%APP%\\venv\\Scripts\\python.exe"

if exist "%ROOT%\\portable\\wheels" (
  "%PY%" -m pip install --no-index --find-links "%ROOT%\\portable\\wheels" -r "%APP%\\requirements.txt"
) else (
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r "%APP%\\requirements.txt"
)
popd

echo Setup complete. Run portable\\windows\\run_phoenix.bat
endlocal
