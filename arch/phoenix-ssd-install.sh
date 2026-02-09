#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID:-0}" -ne 0 ]; then
  echo "[phoenix] Please run as root (sudo)."
  exit 1
fi

PHX_FS="${PHX_FS:-ext4}"
PHX_HOSTNAME="${PHX_HOSTNAME:-phoenix-15}"
PHX_USER="${PHX_USER:-phoenix}"
PHX_DATA_LABEL="${PHX_DATA_LABEL:-PHOENIX_DATA}"
PHX_TIMEZONE="${PHX_TIMEZONE:-UTC}"

echo "[phoenix] Phoenix-15 SSD install starting..."
echo "[phoenix] Filesystem: $PHX_FS"
echo "[phoenix] Hostname:   $PHX_HOSTNAME"
echo "[phoenix] User:       $PHX_USER"
echo "[phoenix] Data label: $PHX_DATA_LABEL"

if [ -z "${PHX_EFI_PART:-}" ] || [ -z "${PHX_ROOT_PART:-}" ]; then
  echo "[phoenix] Missing PHX_EFI_PART and/or PHX_ROOT_PART."
  echo "[phoenix] Run: lsblk -f"
  echo "[phoenix] Example:"
  echo "  export PHX_EFI_PART=/dev/nvme0n1p1"
  echo "  export PHX_ROOT_PART=/dev/nvme0n1p6"
  exit 1
fi

DATA_DEV=""
if [ -n "${PHX_DATA_DEVICE:-}" ]; then
  DATA_DEV="$PHX_DATA_DEVICE"
else
  DATA_DEV="$(lsblk -rpo NAME,LABEL | awk -v label="$PHX_DATA_LABEL" '$2==label {print $1; exit}')"
fi
if [ -z "$DATA_DEV" ]; then
  echo "[phoenix] Data USB not found. Plug it in or set PHX_DATA_DEVICE."
  exit 1
fi

mkdir -p /mnt/phoenix-data
mount "$DATA_DEV" /mnt/phoenix-data

if [ -z "${PHX_REPO_SRC:-}" ]; then
  for candidate in \
    "/mnt/phoenix-data/PHOENIX_TRANSFER/Bjorgsun-26" \
    "/mnt/phoenix-data/Bjorgsun-26"; do
    if [ -d "$candidate/app" ]; then
      PHX_REPO_SRC="$candidate"
      break
    fi
  done
fi
if [ -z "${PHX_REPO_SRC:-}" ] || [ ! -d "$PHX_REPO_SRC/app" ]; then
  echo "[phoenix] Repo source not found."
  echo "[phoenix] Set PHX_REPO_SRC to the Bjorgsun-26 folder on the Data USB."
  exit 1
fi

echo "[phoenix] Formatting root partition: $PHX_ROOT_PART"
if [ "$PHX_FS" = "btrfs" ]; then
  mkfs.btrfs -f "$PHX_ROOT_PART"
else
  mkfs.ext4 -F "$PHX_ROOT_PART"
fi

echo "[phoenix] Mounting partitions..."
mount "$PHX_ROOT_PART" /mnt
mkdir -p /mnt/boot
mount "$PHX_EFI_PART" /mnt/boot

echo "[phoenix] Installing base system..."
pacstrap /mnt \
  base base-devel linux linux-firmware \
  networkmanager sddm xfce4 xfce4-goodies \
  plymouth chromium \
  python python-pip python-virtualenv \
  nodejs npm git rsync \
  exfatprogs curl

genfstab -U /mnt >> /mnt/etc/fstab

echo "[phoenix] Copying Phoenix-15 repo to /opt/Bjorgsun-26..."
mkdir -p /mnt/opt/Bjorgsun-26
rsync -a --delete "$PHX_REPO_SRC/" /mnt/opt/Bjorgsun-26/

echo "[phoenix] Running postinstall..."
arch-chroot /mnt /bin/bash -c \
  "PHX_ROOT_PART='$PHX_ROOT_PART' PHX_HOSTNAME='$PHX_HOSTNAME' PHX_USER='$PHX_USER' PHX_DATA_LABEL='$PHX_DATA_LABEL' PHX_TIMEZONE='$PHX_TIMEZONE' /opt/Bjorgsun-26/arch/phoenix-postinstall.sh"

echo "[phoenix] Install complete. You can reboot now."
