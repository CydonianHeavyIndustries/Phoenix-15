#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/os/out"
RUN_TS="$(date -u +"%Y%m%dT%H%M%SZ" 2>/dev/null || date +"%Y%m%d_%H%M%S")"
LOG_FILE="$LOG_DIR/build-iso-ubuntu-$RUN_TS.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

trap 'code=$?; echo "[phoenix-os] Ubuntu build failed (exit $code) at line $LINENO."; exit $code' ERR

echo "[phoenix-os] Ubuntu build helper started: $(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)"
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
  ca-certificates \
  curl \
  git

echo "[phoenix-os] Ensuring scripts are executable..."
chmod +x "$ROOT/os/build_iso.sh" "$ROOT/os/docker/build.sh" 2>/dev/null || true
chmod +x "$ROOT/os/live-build/auto/config" "$ROOT/os/live-build/auto/build" "$ROOT/os/live-build/auto/clean" 2>/dev/null || true
find "$ROOT/os/live-build/config/hooks" -type f -name "*.chroot" -exec chmod +x {} \; 2>/dev/null || true
find "$ROOT/os/live-build/config/includes.chroot/usr/local/bin" -type f -exec chmod +x {} \; 2>/dev/null || true

echo "[phoenix-os] Running ISO build (Docker disabled)..."
export PHX_NO_DOCKER=1
bash "$ROOT/os/build_iso.sh"

echo "[phoenix-os] Ubuntu build helper complete."
