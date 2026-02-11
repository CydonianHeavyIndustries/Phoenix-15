#!/bin/sh
set -e

TRUST="/etc/phoenix/usb_trust.list"
mkdir -p /etc/phoenix
touch "$TRUST"

list_usb() {
  if command -v lsusb >/dev/null 2>&1; then
    lsusb
  else
    echo "lsusb not available."
  fi
}

list_trust() {
  grep -v '^\s*$' "$TRUST" || true
}

add_trust() {
  ID="$1"
  [ -n "$ID" ] && echo "$ID" >> "$TRUST"
}

remove_trust() {
  ID="$1"
  [ -n "$ID" ] && grep -v "^$ID$" "$TRUST" > "$TRUST.tmp" && mv "$TRUST.tmp" "$TRUST"
}

if command -v zenity >/dev/null 2>&1; then
  CHOICE=$(zenity --list --title="Phoenix USB Trust List" --width=600 --height=360 \
    --column="Action" \
    "Show Connected USB" \
    "Show Trusted USB" \
    "Add Trusted USB (idVendor:idProduct)" \
    "Remove Trusted USB")
  case "$CHOICE" in
    "Show Connected USB")
      list_usb | zenity --text-info --title="Connected USB" --width=700 --height=400 ;;
    "Show Trusted USB")
      list_trust | zenity --text-info --title="Trusted USB" --width=600 --height=300 ;;
    "Add Trusted USB (idVendor:idProduct)")
      ID=$(zenity --entry --title="Add USB ID" --text="Example: 1234:abcd")
      add_trust "$ID" ;;
    "Remove Trusted USB")
      ID=$(list_trust | zenity --list --title="Remove USB ID" --width=520 --height=320 --column="USB ID")
      remove_trust "$ID" ;;
  esac
  exit 0
fi

case "${1:-}" in
  list) list_trust ;;
  add) add_trust "$2" ;;
  remove) remove_trust "$2" ;;
  usb) list_usb ;;
  *) echo "Usage: phoenix-usb-trust.sh {list|add <id>|remove <id>|usb}" ;;
esac
