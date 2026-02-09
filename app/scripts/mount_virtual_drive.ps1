# Mounts the Bjorgsun secure VHDX if not already mounted.
# Uses VIRTUAL_DRIVE_PATH from ../.env if present, else defaults to <project>\Bjorgsun-26v1.vhdx.

Param(
    [string]$DriveLetter = "G"
)

function Get-EnvPath {
    try {
        $envFile = Join-Path (Split-Path -Parent $PSCommandPath) "..\..\.env" | Resolve-Path -ErrorAction Stop
        $line = Get-Content $envFile | Where-Object { $_ -match "^VIRTUAL_DRIVE_PATH=" } | Select-Object -First 1
        if ($line) {
            return $line -replace "^VIRTUAL_DRIVE_PATH=", ""
        }
    } catch {}
    return ""
}

$vhdPath = Get-EnvPath
if (-not $vhdPath) {
    $projectRoot = Resolve-Path (Join-Path (Split-Path -Parent $PSCommandPath) "..\..")
    $vhdPath = Join-Path $projectRoot "Bjorgsun-26v1.vhdx"
}

Write-Host "Checking virtual drive at $vhdPath for letter $DriveLetter..."

if (Get-PSDrive -Name $DriveLetter -ErrorAction SilentlyContinue) {
    Write-Host "Drive $DriveLetter`: already mounted."
    exit 0
}

if (-not (Test-Path $vhdPath)) {
    Write-Host "? VHDX not found at $vhdPath" -ForegroundColor Red
    exit 1
}

try {
    Mount-VHD -Path $vhdPath -ErrorAction Stop | Out-Null
} catch {
    Write-Host "? Mount-VHD failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

try {
    $img = Get-DiskImage -ImagePath $vhdPath -ErrorAction Stop
    $disk = Get-Disk | Where-Object { $_.Number -eq $img.Number }
    if ($disk -and $disk.PartitionStyle -eq 'RAW') {
        Initialize-Disk -Number $disk.Number -PartitionStyle GPT -ErrorAction Stop
    }
    $part = Get-Partition -DiskNumber $disk.Number | Sort-Object Size -Descending | Select-Object -First 1
    if ($part.DriveLetter -ne $DriveLetter) {
        Set-Partition -DiskNumber $disk.Number -PartitionNumber $part.PartitionNumber -NewDriveLetter $DriveLetter -ErrorAction Stop
    }
    if ((Get-Volume -Partition $part).HealthStatus -ne 'Healthy') {
        Repair-Volume -DriveLetter $DriveLetter -OfflineScan
    }
    Write-Host "? Mounted $vhdPath as $DriveLetter`:"
} catch {
    Write-Host "? Failed to assign drive letter: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}


