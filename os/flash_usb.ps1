$ErrorActionPreference = "Stop"

param(
  [string]$IsoPath = "C:\BjorgProj\Bjorgsun-26\os\out\phoenix-15.iso",
  [string]$DriveLetter = "F",
  [switch]$Force
)

if (-not (Test-Path $IsoPath)) {
  Write-Host "ISO not found at $IsoPath"
  Write-Host "Build it with: os\\build_iso.ps1 (Docker required)."
  exit 1
}

$drive = Get-Volume -DriveLetter $DriveLetter -ErrorAction SilentlyContinue
if (-not $drive) {
  Write-Host "Drive $DriveLetter not found."
  exit 1
}

if (-not $Force) {
  Write-Host "This will FORMAT drive $DriveLetter: and erase all data."
  Write-Host "Re-run with -Force to proceed."
  exit 1
}

Write-Host "Formatting $DriveLetter: ..."
Format-Volume -DriveLetter $DriveLetter -FileSystem FAT32 -NewFileSystemLabel "PHOENIX-15" -Force | Out-Null

Write-Host "Mounting ISO..."
$img = Mount-DiskImage -ImagePath $IsoPath -PassThru
$vol = ($img | Get-Volume | Select-Object -First 1)
if (-not $vol) {
  Dismount-DiskImage -ImagePath $IsoPath
  throw "Failed to mount ISO."
}

$isoDrive = $vol.DriveLetter + ":"
Write-Host "Copying ISO contents to $DriveLetter: ..."
robocopy "$isoDrive\\" "$DriveLetter:\\" /MIR /R:1 /W:1 /MT:8 | Out-Null

Dismount-DiskImage -ImagePath $IsoPath

Write-Host "Done. $DriveLetter: should now be UEFI-bootable."
