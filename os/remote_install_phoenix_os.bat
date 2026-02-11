@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Phoenix-15 Remote Ubuntu Installer

set "TRIGGER_FILE=%~dp0remote_upload_begin.flag"

cls
echo ============================================================
echo               Phoenix-15 Remote Ubuntu Installer
echo ============================================================
echo.
echo This script runs on THIS Windows machine and prepares/builds
echo Phoenix-15 OS on another Ubuntu machine over SSH.
echo.
echo Before continuing, on the Ubuntu machine make sure:
echo   1. Ubuntu install is complete and user login works.
echo   2. Network is connected to the same LAN.
echo   3. SSH server is installed and running:
echo      sudo apt update ^&^& sudo apt install -y openssh-server
echo      sudo systemctl enable --now ssh
echo   4. You know the target IP:
echo      hostname -I
echo.
if /I "%~1"=="--now" goto preflight
echo Waiting for external trigger...
echo Keep this window open.
echo.
echo To begin upload from another window, run:
echo   "%~dp0remote_install_begin_upload.bat"
echo.
echo Trigger file:
echo   %TRIGGER_FILE%
echo.
:wait_for_trigger
if exist "%TRIGGER_FILE%" (
  del /q "%TRIGGER_FILE%" >nul 2>&1
  echo Trigger received. Starting setup...
  goto preflight
)
timeout /t 2 >nul
goto wait_for_trigger

:preflight

where ssh >nul 2>&1
if errorlevel 1 (
  echo [ERROR] OpenSSH client not found on this Windows machine.
  echo Install "OpenSSH Client" optional feature, then retry.
  goto :fail
)

where scp >nul 2>&1
if errorlevel 1 (
  echo [ERROR] scp not found on this Windows machine.
  echo Install "OpenSSH Client" optional feature, then retry.
  goto :fail
)

echo.
set "TARGET_HOST=%PHX_TARGET_HOST%"
if not "%TARGET_HOST%"=="" echo Target Ubuntu IP or hostname: %TARGET_HOST% (from PHX_TARGET_HOST)
if "%TARGET_HOST%"=="" set /p TARGET_HOST=Target Ubuntu IP or hostname: 
if "%TARGET_HOST%"=="" (
  echo [ERROR] Target host is required.
  goto :fail
)

set "TARGET_USER=%PHX_TARGET_USER%"
if not "%TARGET_USER%"=="" echo Target SSH user: %TARGET_USER% (from PHX_TARGET_USER)
if "%TARGET_USER%"=="" set /p TARGET_USER=Target SSH user [ubuntu]: 
if "%TARGET_USER%"=="" set "TARGET_USER=ubuntu"

set "REPO_URL=%PHX_REPO_URL%"
if not "%REPO_URL%"=="" echo Repo URL: %REPO_URL% (from PHX_REPO_URL)
if "%REPO_URL%"=="" set /p REPO_URL=Repo URL [https://github.com/CydonianHeavyIndustries/Phoenix-15.git]: 
if "%REPO_URL%"=="" set "REPO_URL=https://github.com/CydonianHeavyIndustries/Phoenix-15.git"

set "BRANCH=%PHX_BRANCH%"
if not "%BRANCH%"=="" echo Branch: %BRANCH% (from PHX_BRANCH)
if "%BRANCH%"=="" set /p BRANCH=Branch [main]: 
if "%BRANCH%"=="" set "BRANCH=main"

set "TARGET_DIR=%PHX_TARGET_DIR%"
if not "%TARGET_DIR%"=="" echo Target workspace: %TARGET_DIR% (from PHX_TARGET_DIR)
if "%TARGET_DIR%"=="" set /p TARGET_DIR=Target workspace [~/Phoenix-15]: 
if "%TARGET_DIR%"=="" set "TARGET_DIR=~/Phoenix-15"
set "TARGET_DIR_REMOTE=%TARGET_DIR%"
set "TARGET_DIR_COPY=%TARGET_DIR%"
if "%TARGET_DIR%"=="~" set "TARGET_DIR_COPY=/home/%TARGET_USER%"
if "%TARGET_DIR:~0,2%"=="~/" set "TARGET_DIR_COPY=/home/%TARGET_USER%/%TARGET_DIR:~2%"
if "%TARGET_DIR%"=="~" set "TARGET_DIR_REMOTE=/home/%TARGET_USER%"
if "%TARGET_DIR:~0,2%"=="~/" set "TARGET_DIR_REMOTE=/home/%TARGET_USER%/%TARGET_DIR:~2%"

echo.
echo [1/5] Testing SSH connectivity...
ssh -o BatchMode=no -o ConnectTimeout=8 "%TARGET_USER%@%TARGET_HOST%" "echo [remote] connected: $(hostname)"
if errorlevel 1 (
  echo [ERROR] Could not connect via SSH.
  goto :fail
)

set "REMOTE_SCRIPT=%TEMP%\phoenix_remote_setup_%RANDOM%%RANDOM%.sh"

echo [2/5] Writing remote setup script...
(
  echo #!/usr/bin/env bash
  echo set -euo pipefail
  echo REPO_URL='%REPO_URL%'
  echo BRANCH='%BRANCH%'
  echo TARGET_DIR='%TARGET_DIR_REMOTE%'
  echo echo "[phoenix] Updating apt..."
  echo sudo apt-get update
  echo sudo apt-get install -y git curl ca-certificates rsync dos2unix live-build debootstrap xorriso syslinux grub-pc-bin grub-efi-amd64-bin mtools dosfstools squashfs-tools
  echo echo "[phoenix] Preparing workspace..."
  echo rm -rf "$TARGET_DIR"
  echo git clone --depth 1 --filter=blob:none --sparse --single-branch --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
  echo cd "$TARGET_DIR"
  echo git sparse-checkout set os
  echo bash os/bootstrap_iso_workspace.sh --force --target "$TARGET_DIR" --branch "$BRANCH" --repo "$REPO_URL"
  echo if [ ! -f "$TARGET_DIR/os/build_iso_ubuntu.sh" ]; then echo "[phoenix] Missing build script: $TARGET_DIR/os/build_iso_ubuntu.sh"; exit 1; fi
  echo ls -l "$TARGET_DIR/os/build_iso_ubuntu.sh" ^| cat
  echo echo "[phoenix] Running ISO build..."
  echo bash "$TARGET_DIR/os/build_iso_ubuntu.sh"
  echo echo "[phoenix] Build complete."
  echo echo "[phoenix] ISO path: $TARGET_DIR/os/out/phoenix-15.iso"
) > "%REMOTE_SCRIPT%"
if errorlevel 1 (
  echo [ERROR] Failed creating temporary remote script.
  goto :fail
)

echo [3/5] Uploading setup script to target...
scp "%REMOTE_SCRIPT%" "%TARGET_USER%@%TARGET_HOST%:~/phoenix_remote_setup.sh"
if errorlevel 1 (
  echo [ERROR] Upload failed.
  del /q "%REMOTE_SCRIPT%" >nul 2>&1
  goto :fail
)
del /q "%REMOTE_SCRIPT%" >nul 2>&1

echo [4/5] Running remote setup/build (you may be prompted for sudo password)...
ssh -tt "%TARGET_USER%@%TARGET_HOST%" "sed -i 's/\r$//' ~/phoenix_remote_setup.sh 2>/dev/null || true; chmod +x ~/phoenix_remote_setup.sh && bash ~/phoenix_remote_setup.sh"
if errorlevel 1 (
  echo [ERROR] Remote build failed. Check remote logs:
  echo        %TARGET_DIR_REMOTE%/os/out/build-iso.log
  echo [INFO] Showing remote build log tail if available...
  ssh "%TARGET_USER%@%TARGET_HOST%" "tail -n 120 %TARGET_DIR_REMOTE%/os/out/build-iso.log 2>/dev/null || echo '[phoenix] build-iso.log not found'"
  goto :fail
)

echo [5/5] Remote build finished.
echo.
set "COPY_BACK="
set /p COPY_BACK=Copy ISO back to this Windows machine now? [Y/n]: 
if /I not "%COPY_BACK%"=="n" (
  set "LOCAL_OUT=C:\BjorgProj\iso_out"
  if not exist "!LOCAL_OUT!" mkdir "!LOCAL_OUT!" >nul 2>&1
  scp "%TARGET_USER%@%TARGET_HOST%:%TARGET_DIR_COPY%/os/out/phoenix-15.iso" "!LOCAL_OUT!\phoenix-15.iso"
  if errorlevel 1 (
    echo [WARN] Could not auto-copy ISO.
    echo Run this manually:
    echo scp %TARGET_USER%@%TARGET_HOST%:%TARGET_DIR_COPY%/os/out/phoenix-15.iso C:\BjorgProj\iso_out\phoenix-15.iso
  ) else (
    echo ISO copied to C:\BjorgProj\iso_out\phoenix-15.iso
  )
)

echo.
echo ============================================================
echo Completed. You can now flash the ISO with Rufus.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo Installer stopped with errors.
pause
exit /b 1
