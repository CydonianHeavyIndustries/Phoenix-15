#!/bin/sh
set -e

if ! command -v zenity >/dev/null 2>&1; then
  /usr/local/bin/phoenix-os-control.sh settings
  exit 0
fi

CHOICE=$(zenity --list --title="Phoenix Control Center" --width=520 --height=420 \
  --column="Module" \
  "System Settings" \
  "Audio" \
  "Display / Graphics" \
  "Network / WiFi" \
  "Bluetooth" \
  "Power" \
  "Time & Language" \
  "App Manager" \
  "Mail" \
  "Update from USB Zip" \
  "Game Server" \
  "File Manager" \
  "Performance" \
  "Drives")

case "$CHOICE" in
  "System Settings") /usr/local/bin/phoenix-os-control.sh settings ;;
  "Audio") /usr/local/bin/phoenix-os-control.sh audio ;;
  "Display / Graphics") /usr/local/bin/phoenix-os-control.sh display ;;
  "Network / WiFi") /usr/local/bin/phoenix-os-control.sh wifi ;;
  "Bluetooth") /usr/local/bin/phoenix-os-control.sh bluetooth ;;
  "Power") /usr/local/bin/phoenix-os-control.sh power ;;
  "Time & Language") /usr/local/bin/phoenix-os-control.sh time ;;
  "App Manager") /usr/local/bin/phoenix-os-control.sh apps ;;
  "Mail") /usr/local/bin/phoenix-os-control.sh mail ;;
  "Update from USB Zip") /usr/local/bin/phoenix-os-control.sh update ;;
  "Game Server") /usr/local/bin/phoenix-os-control.sh gameserver ;;
  "File Manager") /usr/local/bin/phoenix-os-control.sh files ;;
  "Performance") /usr/local/bin/phoenix-os-control.sh performance ;;
  "Drives") /usr/local/bin/phoenix-os-control.sh drives ;;
esac
