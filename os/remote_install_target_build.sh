#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/CydonianHeavyIndustries/Phoenix-15.git}"
BRANCH="${2:-main}"
TARGET_DIR="${3:-$HOME/Phoenix-15}"

echo "[phoenix] Updating apt..."
sudo apt-get update
sudo apt-get install -y \
  git curl ca-certificates rsync dos2unix \
  live-build debootstrap xorriso syslinux grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools squashfs-tools

echo "[phoenix] Preparing workspace..."
rm -rf "$TARGET_DIR"
git clone --depth 1 --filter=blob:none --sparse --single-branch --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
cd "$TARGET_DIR"
git sparse-checkout set os
bash os/bootstrap_iso_workspace.sh --force --target "$TARGET_DIR" --branch "$BRANCH" --repo "$REPO_URL"

if [ ! -f "$TARGET_DIR/os/build_iso_ubuntu.sh" ]; then
  echo "[phoenix] Missing build script: $TARGET_DIR/os/build_iso_ubuntu.sh"
  exit 1
fi

echo "[phoenix] Running ISO build..."
bash "$TARGET_DIR/os/build_iso_ubuntu.sh"

echo "[phoenix] Build complete."
echo "[phoenix] ISO path: $TARGET_DIR/os/out/phoenix-15.iso"
