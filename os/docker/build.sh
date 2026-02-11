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

export PHX_LB_SKIP_AUTO_CONFIG=1
export PHX_LB_SKIP_AUTO_BUILD=1

lb config \
  --distribution bookworm \
  --architectures amd64 \
  --binary-images iso-hybrid \
  --archive-areas "main contrib non-free-firmware" \
  --debian-installer live \
  --bootappend-live "boot=live components username=phoenix hostname=phoenix-15 locales=en_US.UTF-8 keyboard-layouts=us"

echo "[phoenix-os] Staging app into live-build overlay (tarball)..."
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
APP_TAR="$STAGE_DIR/phoenix-app.tar.gz"
tar -czf "$APP_TAR" \
  --exclude "node_modules" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude ".pytest_cache" \
  --exclude ".mypy_cache" \
  --exclude ".ruff_cache" \
  --exclude ".cache" \
  --exclude "logs" \
  --exclude "app/.env" \
  --exclude "app/.env.*" \
  --exclude "app/data/users" \
  --exclude "app/data/memory_exports" \
  --exclude "app/data/session_logs" \
  --exclude "app/data/memory.json" \
  --exclude "app/data/visual_memory.json" \
  --exclude "app/data/preferences_log.json" \
  --exclude "app/data/secrets_hashed.json" \
  --exclude "app/data/audit.log" \
  --exclude "app/data/ui_layout.json" \
  --exclude "app/data/ui_settings.json" \
  --exclude "app/data/Bjorgsun26_memory_handoff.json" \
  -C "$ROOT" app

find "$LIVE_DIR/config/hooks" -type f -name "*.chroot" -exec chmod +x {} \; 2>/dev/null || true
find "$LIVE_DIR/config/includes.chroot/usr/local/bin" -type f -exec chmod +x {} \; 2>/dev/null || true

lb build

ISO=""
if [ -d "$LIVE_DIR" ]; then
  ISO="$(find "$LIVE_DIR" -type f -name "live-image-*.hybrid.iso" | head -n1 || true)"
  if [ -z "$ISO" ]; then
    ISO="$(find "$LIVE_DIR" -type f -name "*.iso" | head -n1 || true)"
  fi
fi
if [ -z "$ISO" ]; then
  ISO="$(find "$ROOT" -type f -name "live-image-*.hybrid.iso" | head -n1 || true)"
fi
if [ -z "$ISO" ]; then
  ISO="$(find "$ROOT" -type f -name "*.iso" | head -n1 || true)"
fi
if [ -z "$ISO" ]; then
  echo "[phoenix-os] ISO not found after build."
  echo "[phoenix-os] Searched: $LIVE_DIR and $ROOT (no maxdepth)."
  echo "[phoenix-os] Dumping live-build output tree (depth 3):"
  find "$LIVE_DIR" -maxdepth 3 -type f | sed 's/^/[phoenix-os] /'
  exit 1
fi

cp -f "$ISO" "$OUT_DIR/phoenix-15.iso"
echo "[phoenix-os] ISO written to $OUT_DIR/phoenix-15.iso"
echo "[phoenix-os] Source ISO: $ISO"
