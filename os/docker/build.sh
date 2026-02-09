#!/usr/bin/env bash
set -euo pipefail

ROOT="${PHX_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
LIVE_DIR="$ROOT/os/live-build"
OUT_DIR="$ROOT/os/out"
STAGE_DIR="$LIVE_DIR/config/includes.chroot/opt/phoenix"

mkdir -p "$OUT_DIR"
mkdir -p "$LIVE_DIR/config/includes.chroot"

echo "[phoenix-os] Staging app into live-build overlay..."
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
rsync -a --delete "$ROOT/app/" "$STAGE_DIR/app/"

rm -f "$STAGE_DIR/app/.env" "$STAGE_DIR/app/.env."* 2>/dev/null || true
rm -rf "$STAGE_DIR/app/logs" 2>/dev/null || true
rm -rf "$STAGE_DIR/app/data/users" 2>/dev/null || true
rm -rf "$STAGE_DIR/app/data/memory_exports" 2>/dev/null || true
rm -rf "$STAGE_DIR/app/data/session_logs" 2>/dev/null || true
rm -f "$STAGE_DIR/app/data/memory.json" 2>/dev/null || true
rm -f "$STAGE_DIR/app/data/visual_memory.json" 2>/dev/null || true
rm -f "$STAGE_DIR/app/data/preferences_log.json" 2>/dev/null || true
rm -f "$STAGE_DIR/app/data/secrets_hashed.json" 2>/dev/null || true
rm -f "$STAGE_DIR/app/data/audit.log" 2>/dev/null || true
rm -f "$STAGE_DIR/app/data/ui_layout.json" 2>/dev/null || true
rm -f "$STAGE_DIR/app/data/ui_settings.json" 2>/dev/null || true
rm -f "$STAGE_DIR/app/data/Bjorgsun26_memory_handoff.json" 2>/dev/null || true

cd "$LIVE_DIR"
chmod +x auto/config auto/build auto/clean || true
find "$LIVE_DIR/config/hooks" -type f -name "*.chroot" -exec chmod +x {} \; 2>/dev/null || true
find "$LIVE_DIR/config/includes.chroot/usr/local/bin" -type f -exec chmod +x {} \; 2>/dev/null || true

if [ "${PHX_LB_CLEAN:-1}" = "1" ]; then
  ./auto/clean || true
fi

./auto/config
./auto/build

ISO="$(ls -1 live-image-*.hybrid.iso 2>/dev/null | head -n1 || true)"
if [ -z "$ISO" ]; then
  ISO="$(ls -1 *.iso 2>/dev/null | head -n1 || true)"
fi
if [ -z "$ISO" ]; then
  echo "[phoenix-os] ISO not found after build."
  exit 1
fi

cp -f "$ISO" "$OUT_DIR/phoenix-15.iso"
echo "[phoenix-os] ISO written to $OUT_DIR/phoenix-15.iso"
