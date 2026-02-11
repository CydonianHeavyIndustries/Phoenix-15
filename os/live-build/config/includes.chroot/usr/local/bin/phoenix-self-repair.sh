#!/bin/sh
set -e

run_repair() {
  echo "[phoenix-os] Repair: restarting core services"
  systemctl daemon-reload || true
  systemctl restart NetworkManager || true
  systemctl restart phoenix-backend.service || true
  systemctl restart phoenix-ui.service || true
  systemctl restart phoenix-data.service || true
  systemctl restart phoenix-storage-policy.service || true
  systemctl restart phoenix-network-safe.service || true
  echo "[phoenix-os] Repair completed"
}

if command -v zenity >/dev/null 2>&1; then
  if zenity --question --title="Phoenix Self-Repair" --text="Run self-repair now?"; then
    run_repair
    zenity --info --title="Self-Repair" --text="Repair finished. Check system status."
  fi
  exit 0
fi

run_repair
