#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/opt/Bjorgsun-26"
APP_DIR="$ROOT_DIR/app"

echo "[phoenix] Installing base packages..."
sudo pacman -Sy --needed --noconfirm \
  base-devel git rsync \
  python python-pip python-virtualenv \
  nodejs npm \
  chromium \
  sddm xfce4 xfce4-goodies \
  networkmanager \
  plymouth \
  exfatprogs

sudo systemctl enable --now NetworkManager
sudo systemctl enable sddm

echo "[phoenix] Setting up Python venv..."
cd "$APP_DIR"
if [ ! -d "venv" ]; then
  python -m venv venv
fi
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "[phoenix] Building UI..."
cd "$APP_DIR/ui/scifiaihud"
npm install
npm run build

echo "[phoenix] Installing Phoenix theme..."
if [ -f "$ROOT_DIR/arch/phoenix-theme-install.sh" ]; then
  bash "$ROOT_DIR/arch/phoenix-theme-install.sh"
fi

echo "[phoenix] Configuring data mount (if present)..."
if [ -f "$ROOT_DIR/arch/phoenix-data-setup.sh" ]; then
  bash "$ROOT_DIR/arch/phoenix-data-setup.sh"
fi

echo "[phoenix] First boot complete."
