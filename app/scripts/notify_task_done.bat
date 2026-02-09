@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "MESSAGE=%~1"
if "%MESSAGE%"=="" set "MESSAGE=Codex Task Completed"

set "WEBHOOK=%DISCORD_TASK_WEBHOOK%"
if "%WEBHOOK%"=="" set "WEBHOOK=%DISCORD_ALERT_WEBHOOK%"

if "%WEBHOOK%"=="" (
  call :read_env "%~dp0..\..\.env"
  if "!WEBHOOK!"=="" call :read_env "%~dp0..\..\\app\\.env"
)

if "%WEBHOOK%"=="" (
  echo [notify] DISCORD_TASK_WEBHOOK or DISCORD_ALERT_WEBHOOK not set.
  exit /b 0
)

set "DISCORD_TASK_WEBHOOK=%WEBHOOK%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url=$env:DISCORD_TASK_WEBHOOK; if (-not $url) { exit 1 }; $payload=@{content='%MESSAGE%'} | ConvertTo-Json; try { Invoke-RestMethod -Uri $url -Method Post -Body $payload -ContentType 'application/json' | Out-Null; exit 0 } catch { exit 1 }"

endlocal
exit /b 0

:read_env
set "ENV_FILE=%~1"
if not exist "%ENV_FILE%" exit /b 0
for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
  if /I "%%A"=="DISCORD_TASK_WEBHOOK" set "WEBHOOK=%%B"
  if /I "%%A"=="DISCORD_ALERT_WEBHOOK" if "!WEBHOOK!"=="" set "WEBHOOK=%%B"
)
exit /b 0
