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
  bash "$ROOT/os/docker/build.sh"
fi

echo "[phoenix-os] Build log (latest): $LOG_LATEST"
echo "[phoenix-os] Build log (timestamped): $LOG_FILE"
echo "[phoenix-os] ISO output: $ROOT/os/out/phoenix-15.iso"
