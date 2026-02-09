@echo off
setlocal EnableExtensions

echo Stopping Bjorgsun-26 processes...

rem Stop python processes tied to this project
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*Bjorgsun-26*' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }"

rem Stop Node processes tied to this project (UI build/dev)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'node*' -or $_.Name -like 'npm*') -and $_.CommandLine -like '*scifiaihud*' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }"

echo Done.
endlocal
