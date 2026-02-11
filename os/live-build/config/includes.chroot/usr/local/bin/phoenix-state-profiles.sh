#!/bin/sh
set -e

set_profile() {
  PROFILE="$1"
  if command -v powerprofilesctl >/dev/null 2>&1; then
    powerprofilesctl set "$PROFILE" >/dev/null 2>&1 || true
  fi
  echo "Profile set: $PROFILE"
}

if command -v zenity >/dev/null 2>&1; then
  CHOICE=$(zenity --list --title="Phoenix State Profiles" --width=520 --height=280 \
    --column="Profile" \
    "power-saver" \
    "balanced" \
    "performance")
  [ -n "$CHOICE" ] && set_profile "$CHOICE"
  exit 0
fi

case "${1:-}" in
  power-saver|balanced|performance) set_profile "$1" ;;
  *) echo "Usage: phoenix-state-profiles.sh {power-saver|balanced|performance}" ;;
esac
