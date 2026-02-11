#!/bin/sh
set -e

LABEL="${PHX_DATA_LABEL:-PHX_DATA}"
MOUNT_DIR="${PHX_DATA_DIR:-/phoenix-data}"

DEVICE="$(blkid -L "$LABEL" 2>/dev/null || true)"
if [ -z "$DEVICE" ]; then
  exit 0
fi

mkdir -p "$MOUNT_DIR"
if ! mountpoint -q "$MOUNT_DIR"; then
  mount -t exfat "$DEVICE" "$MOUNT_DIR" || true
fi

mkdir -p "$MOUNT_DIR/phoenix"
mkdir -p "$MOUNT_DIR/phoenix_update"

if [ -f /etc/phoenix/storage_policy.json ] && [ ! -f "$MOUNT_DIR/phoenix/storage_policy.json" ]; then
  cp /etc/phoenix/storage_policy.json "$MOUNT_DIR/phoenix/storage_policy.json" || true
fi

if id phoenix >/dev/null 2>&1; then
  chown -R phoenix:phoenix "$MOUNT_DIR" || true
fi
