#!/usr/bin/env bash
set -euo pipefail

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$SRC_ROOT"

NEEDS_RELOCATE=0
if [[ "$SRC_ROOT" == /mnt/* ]]; then
  NEEDS_RELOCATE=1
elif command -v findmnt >/dev/null 2>&1; then
  if findmnt -no OPTIONS --target "$SRC_ROOT" 2>/dev/null | tr ',' '\n' | grep -q '^noexec$'; then
    NEEDS_RELOCATE=1
  fi
elif command -v mountpoint >/dev/null 2>&1 && command -v mount >/dev/null 2>&1; then
  MNT_LINE="$(mount | awk -v p="$SRC_ROOT" '$3==p {print $0}')"
  echo "$MNT_LINE" | grep -q 'noexec' && NEEDS_RELOCATE=1 || true
fi

if [ -z "${PHX_BUILD_RELOCATED:-}" ] && [ "$NEEDS_RELOCATE" -eq 1 ]; then
  export PHX_BUILD_RELOCATED=1
  WORK_ROOT="${PHX_BUILD_ROOT:-$HOME/phoenix-build}"
  echo "[phoenix-os] Detected Windows mount ($SRC_ROOT). Relocating build to $WORK_ROOT ..."
  rm -rf "$WORK_ROOT"
  mkdir -p "$WORK_ROOT/app" "$WORK_ROOT/os"
  rsync -a --delete \
    --exclude "node_modules/" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude ".pytest_cache/" \
    --exclude ".mypy_cache/" \
    --exclude ".ruff_cache/" \
    --exclude ".cache/" \
    --exclude "logs/" \
    "$SRC_ROOT/app/" "$WORK_ROOT/app/"
  rsync -a --delete "$SRC_ROOT/os/" "$WORK_ROOT/os/"
  exec bash "$WORK_ROOT/os/build_iso_ubuntu.sh"
fi

LOG_DIR="$ROOT/os/out"
RUN_TS="$(date -u +"%Y%m%dT%H%M%SZ" 2>/dev/null || date +"%Y%m%d_%H%M%S")"
LOG_FILE="$LOG_DIR/build-iso-ubuntu-$RUN_TS.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

trap 'code=$?; echo "[phoenix-os] Ubuntu build failed (exit $code) at line $LINENO."; exit $code' ERR

echo "[phoenix-os] Ubuntu build helper started: $(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)"
echo "[phoenix-os] Root: $ROOT"
echo "[phoenix-os] Log file: $LOG_FILE"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "[phoenix-os] apt-get not found. This helper targets Ubuntu/Debian."
  exit 1
fi

echo "[phoenix-os] Installing build dependencies..."
sudo apt-get update
sudo apt-get install -y \
  live-build \
  xorriso \
  squashfs-tools \
  debootstrap \
  rsync \
  dos2unix \
  debian-archive-keyring \
  ca-certificates \
  curl \
  git

echo "[phoenix-os] Ensuring scripts are executable..."
dos2unix "$ROOT/os/build_iso.sh" "$ROOT/os/docker/build.sh" "$ROOT/os/live-build/auto/config" "$ROOT/os/live-build/auto/build" "$ROOT/os/live-build/auto/clean" 2>/dev/null || true
chmod +x "$ROOT/os/build_iso.sh" "$ROOT/os/docker/build.sh" 2>/dev/null || true
chmod +x "$ROOT/os/live-build/auto/config" "$ROOT/os/live-build/auto/build" "$ROOT/os/live-build/auto/clean" 2>/dev/null || true
find "$ROOT/os/live-build/config/hooks" -type f -name "*.chroot" -exec chmod +x {} \; 2>/dev/null || true
find "$ROOT/os/live-build/config/includes.chroot/usr/local/bin" -type f -exec chmod +x {} \; 2>/dev/null || true

echo "[phoenix-os] Running ISO build (Docker disabled)..."
export PHX_NO_DOCKER=1
bash "$ROOT/os/build_iso.sh"

echo "[phoenix-os] Ubuntu build helper complete."
