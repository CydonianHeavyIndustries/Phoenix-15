#!/bin/sh
set -e

FLAG="/etc/phoenix/network_safe_mode"

apply_off() {
  if command -v nmcli >/dev/null 2>&1; then
    nmcli networking off || true
  else
    systemctl stop NetworkManager || true
  fi
}

apply_on() {
  if command -v nmcli >/dev/null 2>&1; then
    nmcli networking on || true
  else
    systemctl start NetworkManager || true
  fi
}

case "$1" in
  enable)
    mkdir -p /etc/phoenix
    touch "$FLAG"
    apply_off
    ;;
  disable)
    rm -f "$FLAG"
    apply_on
    ;;
  status)
    if [ -f "$FLAG" ]; then
      echo "safe"
      exit 0
    fi
    echo "normal"
    exit 0
    ;;
  *)
    if [ -f "$FLAG" ]; then
      rm -f "$FLAG"
      apply_on
      echo "Network safe mode: OFF"
    else
      mkdir -p /etc/phoenix
      touch "$FLAG"
      apply_off
      echo "Network safe mode: ON"
    fi
    ;;
esac
