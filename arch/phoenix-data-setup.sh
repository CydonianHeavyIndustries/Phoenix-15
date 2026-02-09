#!/usr/bin/env bash
set -euo pipefail

PHX_DATA_LABEL="${PHX_DATA_LABEL:-PHOENIX_DATA}"
MOUNT_POINT="/phoenix-data"

echo "[phoenix] Setting up data mount for label: $PHX_DATA_LABEL"
mkdir -p "$MOUNT_POINT"

if ! grep -q "$MOUNT_POINT" /etc/fstab; then
  echo "LABEL=${PHX_DATA_LABEL} ${MOUNT_POINT} exfat rw,nofail,x-systemd.automount,uid=1000,gid=1000,umask=022 0 2" >> /etc/fstab
fi

echo "[phoenix] Data mount configured."
