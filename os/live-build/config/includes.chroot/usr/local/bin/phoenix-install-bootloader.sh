#!/bin/sh
set -e

echo "[phoenix-os] Installing bootloader..."
if command -v grub-install >/dev/null 2>&1; then
  if [ -d /sys/firmware/efi ]; then
    apt-get update
    apt-get install -y grub-efi-amd64
    grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=Phoenix
  else
    apt-get update
    apt-get install -y grub-pc
    grub-install /dev/sda || true
  fi
  update-grub || true
fi
