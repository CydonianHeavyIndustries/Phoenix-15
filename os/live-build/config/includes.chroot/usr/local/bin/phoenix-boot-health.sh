#!/bin/sh
set -e

OUT="/tmp/phoenix_boot_health.txt"
{
  echo "Phoenix Boot Health"
  echo "==================="
  echo ""
  echo "Failed services:"
  systemctl --failed || true
  echo ""
  echo "Phoenix services:"
  for svc in phoenix-backend.service phoenix-ui.service phoenix-data.service phoenix-storage-policy.service phoenix-network-safe.service; do
    if systemctl list-unit-files | grep -q "^$svc"; then
      STATE=$(systemctl is-active "$svc" 2>/dev/null || true)
      echo "  $svc: $STATE"
    else
      echo "  $svc: not installed"
    fi
  done
  echo ""
  echo "Disk usage:"
  df -h /
} > "$OUT"

if command -v zenity >/dev/null 2>&1; then
  zenity --text-info --title="Phoenix Boot Health" --width=700 --height=500 --filename="$OUT"
else
  cat "$OUT"
fi
