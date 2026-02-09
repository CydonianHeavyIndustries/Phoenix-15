#!/usr/bin/env bash
set -euo pipefail

BASE="/phoenix-users"
mkdir -p "$BASE"

echo "[phoenix] Scanning for PHOENIX_USER_* USB drives..."
while read -r dev label; do
  [ -z "$dev" ] && continue
  mountpoint="$BASE/${label}"
  mkdir -p "$mountpoint"
  if ! mountpoint -q "$mountpoint"; then
    mount "$dev" "$mountpoint" || true
  fi
done < <(lsblk -rpo NAME,LABEL | awk '$2 ~ /^PHOENIX_USER_/ {print $1, $2}')

echo "[phoenix] User USB scan complete."
