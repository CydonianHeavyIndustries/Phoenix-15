#!/bin/sh
set -e

LOG_PATH="/var/log/phoenix_install.log"

log() {
  TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)
  echo "[$TS] $*" | tee -a "$LOG_PATH" >/dev/null 2>&1 || true
}

usage() {
  cat <<'USAGE'
Phoenix-15 Disk Install (FULL WIPE)

Usage:
  phoenix-disk-install.sh --disk /dev/sdX --execute

Options:
  --disk    Target disk (FULL WIPE, GPT repartition)
  --execute Required to perform destructive actions
  --dry-run Print steps without executing (default)

This script is designed for the Phoenix-15 live USB.
USAGE
}

DISK=""
EXECUTE=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --disk)
      DISK="$2"
      shift 2
      ;;
    --execute)
      EXECUTE=1
      shift
      ;;
    --dry-run)
      EXECUTE=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      usage
      exit 1
      ;;
  esac
done

if [ -z "$DISK" ]; then
  echo "Available disks:"
  lsblk -d -o NAME,SIZE,MODEL,TYPE,TRAN
  usage
  exit 1
fi

if [ ! -b "$DISK" ]; then
  echo "Disk not found: $DISK"
  exit 1
fi

if [ "$EXECUTE" -ne 1 ]; then
  echo "Dry run only. Re-run with --execute to proceed."
  echo "Target disk: $DISK"
  exit 0
fi

log "install_begin disk=$DISK"

EFI_PART="${DISK}1"
ROOT_PART="${DISK}2"

log "wipe_gpt"
sgdisk --zap-all "$DISK"

log "partition_gpt"
sgdisk -n 1:1M:+512M -t 1:EF00 -c 1:PHX_EFI "$DISK"
sgdisk -n 2:0:0 -t 2:8300 -c 2:PHX_ROOT "$DISK"
partprobe "$DISK" || true
sleep 2

log "format_partitions"
mkfs.fat -F32 "$EFI_PART"
mkfs.ext4 -F "$ROOT_PART"

log "mount_root"
mkdir -p /mnt/phoenix
mount "$ROOT_PART" /mnt/phoenix
mkdir -p /mnt/phoenix/boot/efi
mount "$EFI_PART" /mnt/phoenix/boot/efi

log "rsync_root"
rsync -aHAX --numeric-ids \
  --exclude=/dev/* \
  --exclude=/proc/* \
  --exclude=/sys/* \
  --exclude=/run/* \
  --exclude=/tmp/* \
  --exclude=/mnt/* \
  --exclude=/media/* \
  --exclude=/lost+found \
  / /mnt/phoenix

log "install_grub"
mount --bind /dev /mnt/phoenix/dev
mount --bind /proc /mnt/phoenix/proc
mount --bind /sys /mnt/phoenix/sys
chroot /mnt/phoenix /bin/sh -c "phoenix-install-bootloader.sh || true"
chroot /mnt/phoenix /bin/sh -c "update-grub || true"

log "cleanup"
umount /mnt/phoenix/dev || true
umount /mnt/phoenix/proc || true
umount /mnt/phoenix/sys || true
umount /mnt/phoenix/boot/efi || true
umount /mnt/phoenix || true

log "install_done"
echo "Install complete. You can reboot and remove the USB."
