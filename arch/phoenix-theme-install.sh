#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/opt/Bjorgsun-26"
THEME_DIR="$ROOT_DIR/app/phoenix_os_theme"

SUDO=""
if command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
fi

if [ ! -d "$THEME_DIR" ]; then
  echo "[phoenix] Theme pack not found at $THEME_DIR"
  exit 1
fi

echo "[phoenix] Installing SDDM theme..."
$SUDO mkdir -p /usr/share/sddm/themes/phoenix-os
$SUDO rsync -a "$THEME_DIR/sddm/phoenix-os/" /usr/share/sddm/themes/phoenix-os/
$SUDO mkdir -p /etc/sddm.conf.d
$SUDO tee /etc/sddm.conf.d/phoenix.conf >/dev/null <<'EOF'
[Theme]
Current=phoenix-os
EOF

echo "[phoenix] Installing Plymouth theme..."
$SUDO mkdir -p /usr/share/plymouth/themes/phoenix
$SUDO rsync -a "$THEME_DIR/plymouth/phoenix/" /usr/share/plymouth/themes/phoenix/
$SUDO plymouth-set-default-theme -R phoenix || true

echo "[phoenix] Setting wallpaper (XFCE)..."
if command -v xfconf-query >/dev/null 2>&1; then
  WALL="$THEME_DIR/assets/wallpaper/phoenix_wallpaper.png"
  xfconf-query -c xfce4-desktop -l | grep last-image | while read -r prop; do
    xfconf-query -c xfce4-desktop -p "$prop" -s "$WALL" || true
  done
fi

echo "[phoenix] Theme install complete."
