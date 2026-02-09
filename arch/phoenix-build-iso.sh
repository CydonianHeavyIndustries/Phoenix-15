#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo ./phoenix-build-iso.sh"
  exit 1
fi

if ! command -v mkarchiso >/dev/null 2>&1; then
  echo "archiso not found. Install first: pacman -S archiso"
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Locate transfer root and repo
TRANSFER_DIR=""
SOURCE_REPO=""

if [[ -f "$SCRIPT_DIR/phoenix-init.sh" ]]; then
  TRANSFER_DIR="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../phoenix-init.sh" ]]; then
  TRANSFER_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
elif [[ -f "$SCRIPT_DIR/../../phoenix-init.sh" ]]; then
  TRANSFER_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
fi

if [[ -n "$TRANSFER_DIR" && -d "$TRANSFER_DIR/Bjorgsun-26/app/phoenix_os_theme" ]]; then
  SOURCE_REPO="$TRANSFER_DIR/Bjorgsun-26"
elif [[ -d "$SCRIPT_DIR/../app/phoenix_os_theme" ]]; then
  SOURCE_REPO="$(cd -- "$SCRIPT_DIR/.." && pwd)"
  TRANSFER_DIR="$SOURCE_REPO"
fi

PROFILE_BASE="/usr/share/archiso/configs/releng"
WORKDIR="${TRANSFER_DIR}/_iso_work"
OUTDIR="${TRANSFER_DIR}/_iso_out"

if [[ ! -d "$PROFILE_BASE" ]]; then
  echo "Archiso base profile missing: $PROFILE_BASE"
  exit 1
fi

if [[ -z "$SOURCE_REPO" || ! -d "$SOURCE_REPO" ]]; then
  echo "Source repo not found at: $SOURCE_REPO"
  exit 1
fi

rm -rf "$WORKDIR" "$OUTDIR"
mkdir -p "$WORKDIR" "$OUTDIR"
cp -a "$PROFILE_BASE"/. "$WORKDIR"/

# Include installer/update scripts and UI assets in the live environment.
mkdir -p "$WORKDIR/airootfs/root/PHOENIX_TRANSFER"
if [[ -f "$TRANSFER_DIR/phoenix-init.sh" ]]; then
  rsync -a "$TRANSFER_DIR/phoenix-init.sh" "$WORKDIR/airootfs/root/PHOENIX_TRANSFER/"
fi
if [[ -f "$TRANSFER_DIR/phoenix-update.sh" ]]; then
  rsync -a "$TRANSFER_DIR/phoenix-update.sh" "$WORKDIR/airootfs/root/PHOENIX_TRANSFER/"
fi
rsync -a "$SOURCE_REPO/app/phoenix_os_theme" "$WORKDIR/airootfs/root/PHOENIX_TRANSFER/"

# Convenience packages for live install.
echo "networkmanager" >> "$WORKDIR/packages.x86_64"
echo "rsync" >> "$WORKDIR/packages.x86_64"
echo "git" >> "$WORKDIR/packages.x86_64"

mkarchiso -v -w "$WORKDIR/_build" -o "$OUTDIR" "$WORKDIR"

echo
echo "ISO built in: $OUTDIR"
echo "Look for: archlinux-*.iso (rename to phoenix-15.iso if desired)"
