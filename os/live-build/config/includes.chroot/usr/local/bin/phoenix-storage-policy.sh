#!/bin/sh
set -e

POLICY_FILE="${PHX_STORAGE_POLICY:-/phoenix-data/phoenix/storage_policy.json}"
FALLBACK_POLICY="/etc/phoenix/storage_policy.json"
ALLOW_INTERNAL="false"

if [ ! -f "$POLICY_FILE" ] && [ -f "$FALLBACK_POLICY" ]; then
  POLICY_FILE="$FALLBACK_POLICY"
fi

if [ -f "$POLICY_FILE" ]; then
  if command -v jq >/dev/null 2>&1; then
    ALLOW_INTERNAL="$(jq -r '.allow_internal_mounts // false' "$POLICY_FILE" 2>/dev/null || echo false)"
  else
    if grep -qi "allow_internal_mounts" "$POLICY_FILE" && grep -qi "true" "$POLICY_FILE"; then
      ALLOW_INTERNAL="true"
    fi
  fi
fi

if [ "$ALLOW_INTERNAL" = "true" ]; then
  systemctl unmask udisks2 >/dev/null 2>&1 || true
  systemctl start udisks2 >/dev/null 2>&1 || true
  exit 0
fi

systemctl stop udisks2 >/dev/null 2>&1 || true
systemctl mask udisks2 >/dev/null 2>&1 || true

lsblk -rno NAME,MOUNTPOINT,RM,TYPE | while read -r name mountpoint removable type; do
  if [ "$removable" = "0" ] && [ -n "$mountpoint" ]; then
    umount -l "$mountpoint" >/dev/null 2>&1 || true
  fi
done
