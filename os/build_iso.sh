#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="phoenix-15-os"
LOG_DIR="$ROOT/os/out"
RUN_TS="$(date -u +"%Y%m%dT%H%M%SZ" 2>/dev/null || date +"%Y%m%d_%H%M%S")"
LOG_FILE="$LOG_DIR/build-iso-$RUN_TS.log"
LOG_LATEST="$LOG_DIR/build-iso.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE" "$LOG_LATEST") 2>&1

trap 'code=$?; echo "[phoenix-os] Build failed (exit $code) at line $LINENO."; exit $code' ERR

echo "[phoenix-os] Build started: $(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)"
echo "[phoenix-os] Log file: $LOG_FILE"

if command -v dos2unix >/dev/null 2>&1; then
  dos2unix "$ROOT/os/docker/build.sh" "$ROOT/os/live-build/auto/config" "$ROOT/os/live-build/auto/build" "$ROOT/os/live-build/auto/clean" 2>/dev/null || true
fi

USE_DOCKER=1
if [ "${PHX_NO_DOCKER:-0}" = "1" ]; then
  USE_DOCKER=0
fi

if [ "$USE_DOCKER" -eq 1 ] && command -v docker >/dev/null 2>&1; then
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker build -t "$IMAGE" -f "$ROOT/os/docker/Dockerfile" "$ROOT"
  fi
  docker run --rm -e PHX_ROOT=/work -v "$ROOT:/work" "$IMAGE" /work/os/docker/build.sh
else
  if [ "$(id -u)" -ne 0 ]; then
    echo "[phoenix-os] Live-build requires root. Re-running with sudo..."
    exec sudo -E bash "$0"
  fi
  export PHX_ROOT="$ROOT"
  BUILD_SH="$ROOT/os/docker/build.sh"
  echo "[phoenix-os] Using build script: $BUILD_SH"
  if [ ! -r "$BUILD_SH" ]; then
    echo "[phoenix-os] ERROR: build.sh is not readable."
    exit 126
  fi
  ls -l "$BUILD_SH" 2>/dev/null || true
  if ! bash "$BUILD_SH"; then
    code=$?
    echo "[phoenix-os] build.sh exited with $code"
    if [ "$code" -eq 126 ]; then
      echo "[phoenix-os] Attempting fallback: copy build.sh to /tmp and re-run."
      TMP_DIR="$(mktemp -d)"
      cp "$BUILD_SH" "$TMP_DIR/build.sh"
      bash "$TMP_DIR/build.sh"
      exit $?
    fi
    exit "$code"
  fi
fi

echo "[phoenix-os] Build log (latest): $LOG_LATEST"
echo "[phoenix-os] Build log (timestamped): $LOG_FILE"
echo "[phoenix-os] ISO output: $ROOT/os/out/phoenix-15.iso"
