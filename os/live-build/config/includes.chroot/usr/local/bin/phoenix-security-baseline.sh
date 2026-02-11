#!/bin/sh
set -e

apply_baseline() {
  echo "[phoenix-os] Enabling firewall..."
  ufw default deny incoming || true
  ufw default allow outgoing || true
  ufw --force enable || true

  echo "[phoenix-os] Enabling automatic updates..."
  if command -v dpkg-reconfigure >/dev/null 2>&1; then
    printf '%s\n' 'unattended-upgrades unattended-upgrades/enable_auto_updates boolean true' | debconf-set-selections || true
    dpkg-reconfigure -f noninteractive unattended-upgrades || true
  fi

  echo "[phoenix-os] Enabling antivirus updates..."
  systemctl enable --now clamav-freshclam || true
}

if command -v zenity >/dev/null 2>&1; then
  if zenity --question --title="Phoenix Security Baseline" --text="Apply baseline security settings now?"; then
    apply_baseline
    zenity --info --title="Security Baseline" --text="Baseline applied."
  fi
  exit 0
fi

apply_baseline
