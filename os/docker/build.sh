#!/usr/bin/env bash
set -euo pipefail

ROOT="${PHX_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
LIVE_DIR="$ROOT/os/live-build"
OUT_DIR="$ROOT/os/out"
STAGE_DIR="$LIVE_DIR/config/includes.chroot/opt/phoenix"

mkdir -p "$OUT_DIR"
mkdir -p "$LIVE_DIR/config/includes.chroot"

cd "$LIVE_DIR"
chmod +x auto/config auto/build auto/clean || true
find "$LIVE_DIR/config/hooks" -type f -name "*.chroot" -exec chmod +x {} \; 2>/dev/null || true
find "$LIVE_DIR/config/includes.chroot/usr/local/bin" -type f -exec chmod +x {} \; 2>/dev/null || true
rm -f "$LIVE_DIR/auto/.phx_lb_config_running" 2>/dev/null || true
rm -rf "$LIVE_DIR/config/includes.chroot/opt/phoenix/app" 2>/dev/null || true

if [ "${PHX_LB_CLEAN:-1}" = "1" ]; then
  bash ./auto/clean || true
fi

bash ./auto/config

echo "[phoenix-os] Staging app into live-build overlay..."
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
RSYNC_EXCLUDES=(
  --exclude "node_modules/"
  --exclude "__pycache__/"
  --exclude "*.pyc"
  --exclude ".pytest_cache/"
  --exclude ".mypy_cache/"
  --exclude ".ruff_cache/"
  --exclude ".cache/"
  --exclude "logs/"
)
rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$ROOT/app/" "$STAGE_DIR/app/"

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

find "$LIVE_DIR/config/hooks" -type f -name "*.chroot" -exec chmod +x {} \; 2>/dev/null || true
find "$LIVE_DIR/config/includes.chroot/usr/local/bin" -type f -exec chmod +x {} \; 2>/dev/null || true

export PHX_LB_SKIP_AUTO_CONFIG=1
bash ./auto/build

ISO=""
if [ -d "$LIVE_DIR" ]; then
  ISO="$(find "$LIVE_DIR" -maxdepth 2 -type f -name "live-image-*.hybrid.iso" | head -n1 || true)"
  if [ -z "$ISO" ]; then
    ISO="$(find "$LIVE_DIR" -maxdepth 2 -type f -name "*.iso" | head -n1 || true)"
  fi
fi
if [ -z "$ISO" ]; then
  ISO="$(find "$ROOT" -maxdepth 3 -type f -name "live-image-*.hybrid.iso" | head -n1 || true)"
fi
if [ -z "$ISO" ]; then
  ISO="$(find "$ROOT" -maxdepth 3 -type f -name "*.iso" | head -n1 || true)"
fi
if [ -z "$ISO" ]; then
  echo "[phoenix-os] ISO not found after build."
  echo "[phoenix-os] Searched: $LIVE_DIR and $ROOT (maxdepth 3)."
  exit 1
fi

cp -f "$ISO" "$OUT_DIR/phoenix-15.iso"
echo "[phoenix-os] ISO written to $OUT_DIR/phoenix-15.iso"
echo "[phoenix-os] Source ISO: $ISO"
