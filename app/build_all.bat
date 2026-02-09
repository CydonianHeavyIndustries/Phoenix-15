@echo off
setlocal enableextensions enabledelayedexpansion
chcp 65001 >nul
title Bjorgsun-26 One-Click Builder
cd /d "%~dp0"

set "ROOT=%~dp0"
set "DEST=G:\Bjorgsun-26"
set "ICON=%ROOT%ui\assets\Bjorgsunexeicon.ico"

for %%P in ("%ROOT%venv\Scripts\python.exe" "%ROOT%.venv\Scripts\python.exe") do if not defined PYEXE if exist %%P set "PYEXE=%%P"
if not defined PYEXE set "PYEXE=%ROOT%venv\Scripts\python.exe"

echo [*] Ensuring venv exists...
if not exist "%PYEXE%" (
  echo [!] venv not found. Creating one...
  py -3.11 -m venv "%ROOT%venv"
  if not exist "%ROOT%venv\Scripts\python.exe" (
    echo [!] venv creation failed. Please create it manually: py -3.11 -m venv venv
    pause
    exit /b 1
  )
  set "PYEXE=%ROOT%venv\Scripts\python.exe"
)

echo [*] Upgrading pip/setuptools/wheel...
"%PYEXE%" -m pip install --upgrade pip setuptools wheel

echo [*] Installing deps...
"%PYEXE%" -m pip install -r "%ROOT%requirements.txt"
"%PYEXE%" -m pip install -r "%ROOT%server\requirements.txt"

echo [*] Building main EXE (onefile)...
"%PYEXE%" -m PyInstaller "%ROOT%launcher_bjorgsun.py" --onefile --noconfirm --log-level=WARN --console --name Bjorgsun-26 --icon="%ICON%"

echo [*] Building main EXE (onedir)...
"%PYEXE%" -m PyInstaller "%ROOT%launcher_bjorgsun.py" --onedir --noconfirm --log-level=WARN --console --name Bjorgsun-26 --icon="%ICON%"

echo [*] Building setup installer...
"%PYEXE%" -m PyInstaller "%ROOT%installer_bjorgsun.py" --onefile --noconfirm --log-level=WARN --name Bjorgsun-Setup --icon="%ICON%" ^
  --add-data "%ROOT%dist/Bjorgsun-26;payload/dist/Bjorgsun-26" ^
  --add-data "%ROOT%dist/Bjorgsun-26.exe;payload/Bjorgsun-26.exe" ^
  --add-data "%ROOT%launch_stable.bat;payload/launch_stable.bat" ^
  --add-data "%ROOT%launch_dev.bat;payload/launch_dev.bat" ^
  --add-data "%ROOT%Gotosleep.bat;payload/Gotosleep.bat"

echo [*] Copying outputs to %DEST% ...
mkdir "%DEST%\dist" >nul 2>&1
if exist "%ROOT%dist\Bjorgsun-26.exe" copy /Y "%ROOT%dist\Bjorgsun-26.exe" "%DEST%\Bjorgsun-26.exe" >nul
if exist "%ROOT%dist\Bjorgsun-Setup.exe" copy /Y "%ROOT%dist\Bjorgsun-Setup.exe" "%DEST%\Bjorgsun-Setup.exe" >nul
if exist "%ROOT%dist\Bjorgsun-26" robocopy "%ROOT%dist\Bjorgsun-26" "%DEST%\dist\Bjorgsun-26" /E /NFL /NDL /NJH /NJS /NP >nul

echo [?] Build complete. Outputs in %DEST% (and dist/).
pause
endlocal


