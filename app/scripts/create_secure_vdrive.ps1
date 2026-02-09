# Creates and mounts a VHDX as a secure virtual drive (Windows).
# Prompts for path, size, drive letter, and volume name. Double confirmation required.
# Run in an elevated PowerShell window.

Param(
    [string]$VhdPath = "",
    [string]$DriveLetter = "",
    [string]$VolumeName = "BJORGSUN_SECURE",
    [int]$SizeGB = 4
)

Write-Host "=== Bjorgsun Secure Virtual Drive Creator ===" -ForegroundColor Cyan
if (-not $VhdPath) {
    $VhdPath = Read-Host "Choose VHDX file path (e.g., G:\Secure\bjor-secure.vhdx)"
}
if (-not $DriveLetter) {
    $DriveLetter = Read-Host "Choose drive letter (e.g., R)"
}
if (-not $VolumeName) {
    $VolumeName = "BJORGSUN_SECURE"
}
$SizeGB = [int](Read-Host "Size in GB (default 4)" )
if (-not $SizeGB -or $SizeGB -le 0) { $SizeGB = 4 }

Write-Warning "About to create VHDX at $VhdPath, size ${SizeGB}GB, mount as $DriveLetter`:."
$confirm1 = Read-Host "Type CREATE to proceed"
if ($confirm1 -ne "CREATE") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 1
}
$confirm2 = Read-Host "FINAL CONFIRMATION: type YES to format and mount"
if ($confirm2 -ne "YES") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 1
}

try {
    New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($VhdPath)) -Force | Out-Null
    New-VHD -Path $VhdPath -Dynamic -SizeBytes (${SizeGB}GB) -ErrorAction Stop | Out-Null
    Mount-VHD -Path $VhdPath -PassThru -ErrorAction Stop | Initialize-Disk -PartitionStyle GPT -PassThru | `
        New-Partition -DriveLetter $DriveLetter -UseMaximumSize | `
        Format-Volume -FileSystem NTFS -NewFileSystemLabel $VolumeName -Confirm:$false
    Write-Host "✅ Virtual drive created and mounted at $DriveLetter`:\" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
}

