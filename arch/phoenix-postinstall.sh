#!/usr/bin/env bash
set -euo pipefail

PHX_HOSTNAME="${PHX_HOSTNAME:-phoenix-15}"
PHX_USER="${PHX_USER:-phoenix}"
PHX_DATA_LABEL="${PHX_DATA_LABEL:-PHOENIX_DATA}"
PHX_TIMEZONE="${PHX_TIMEZONE:-UTC}"

echo "[phoenix] Setting timezone..."
ln -sf "/usr/share/zoneinfo/${PHX_TIMEZONE}" /etc/localtime
hwclock --systohc

echo "[phoenix] Configuring locale..."
sed -i 's/^#en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf

echo "[phoenix] Setting hostname..."
echo "$PHX_HOSTNAME" > /etc/hostname

echo "[phoenix] Creating user..."
if ! id "$PHX_USER" >/dev/null 2>&1; then
  useradd -m -G wheel -s /bin/bash "$PHX_USER"
fi

if [ -z "${PHX_USER_PASS:-}" ]; then
  read -rsp "Set password for $PHX_USER: " PHX_USER_PASS
  echo
fi
echo "$PHX_USER:$PHX_USER_PASS" | chpasswd

echo "[phoenix] Enabling services..."
systemctl enable NetworkManager
systemctl enable sddm

echo "[phoenix] Installing systemd-boot..."
bootctl --path=/boot install

ROOT_UUID="$(blkid -s UUID -o value "$PHX_ROOT_PART")"
WINDOWS_EFI="/boot/EFI/Microsoft/Boot/bootmgfw.efi"

mkdir -p /boot/loader/entries

if [ -f "$WINDOWS_EFI" ]; then
  cat > /boot/loader/entries/windows.conf <<EOF
title   Windows 11
efi     /EFI/Microsoft/Boot/bootmgfw.efi
EOF
  DEFAULT_ENTRY="windows"
else
  DEFAULT_ENTRY="phoenix"
fi

cat > /boot/loader/entries/phoenix.conf <<EOF
title   Phoenix-15
linux   /vmlinuz-linux
initrd  /initramfs-linux.img
options root=UUID=${ROOT_UUID} rw quiet splash
EOF

cat > /boot/loader/loader.conf <<EOF
default ${DEFAULT_ENTRY}
timeout 2
console-mode max
editor no
EOF

echo "[phoenix] Installing Phoenix theme..."
if [ -f "/opt/Bjorgsun-26/arch/phoenix-theme-install.sh" ]; then
  bash /opt/Bjorgsun-26/arch/phoenix-theme-install.sh
fi

echo "[phoenix] Configuring Phoenix data mount..."
if [ -f "/opt/Bjorgsun-26/arch/phoenix-data-setup.sh" ]; then
  PHX_DATA_LABEL="$PHX_DATA_LABEL" bash /opt/Bjorgsun-26/arch/phoenix-data-setup.sh
fi

echo "[phoenix] Postinstall complete."
