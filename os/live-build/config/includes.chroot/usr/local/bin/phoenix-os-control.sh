#!/bin/sh
set -e

ACTION="$(printf "%s" "$1" | tr 'A-Z' 'a-z')"

open_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    shift
    "$1" "$@" >/dev/null 2>&1 &
    exit 0
  fi
  return 1
}

case "$ACTION" in
  settings)
    open_cmd xfce4-settings-manager && exit 0
    ;;
  audio)
    open_cmd pavucontrol && exit 0
    ;;
  display|graphics)
    open_cmd xfce4-display-settings && exit 0
    ;;
  network|wifi)
    open_cmd nm-connection-editor && exit 0
    ;;
  bluetooth)
    open_cmd blueman-manager && exit 0
    ;;
  power)
    open_cmd xfce4-power-manager-settings && exit 0
    ;;
  time|language|timezone|locale)
    open_cmd xfce4-settings-manager && exit 0
    ;;
  files|folders)
    open_cmd thunar && exit 0
    ;;
  apps|appmanager|installer)
    open_cmd synaptic && exit 0
    ;;
  update|usbupdate)
    open_cmd /usr/local/bin/phoenix-update-from-usb.sh && exit 0
    ;;
  mail|email)
    open_cmd thunderbird && exit 0
    ;;
  integrity|check)
    open_cmd /usr/local/bin/phoenix-integrity-check.sh && exit 0
    ;;
  docs|offline|help)
    open_cmd /usr/local/bin/phoenix-offline-docs.sh && exit 0
    ;;
  network-safe|safemode|safe)
    open_cmd /usr/local/bin/phoenix-network-safe.sh && exit 0
    ;;
  gameserver|game|server)
    open_cmd /usr/local/bin/phoenix-game-server.sh && exit 0
    ;;
  performance|taskmanager)
    open_cmd xfce4-taskmanager && exit 0
    ;;
  drives|storage)
    open_cmd gnome-disk-utility && exit 0
    ;;
  *)
    echo "Unknown action: $ACTION"
    exit 1
    ;;
esac

echo "No handler available for: $ACTION"
exit 1
