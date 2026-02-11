#!/bin/sh
set -e

LOCKFILE="/etc/phoenix/locklist.txt"
mkdir -p /etc/phoenix
touch "$LOCKFILE"

list_locks() {
  grep -v '^\s*$' "$LOCKFILE" || true
}

apply_hold() {
  list_locks | while read -r pkg; do
    [ -n "$pkg" ] && apt-mark hold "$pkg" >/dev/null 2>&1 || true
  done
}

apply_unhold() {
  list_locks | while read -r pkg; do
    [ -n "$pkg" ] && apt-mark unhold "$pkg" >/dev/null 2>&1 || true
  done
}

if command -v zenity >/dev/null 2>&1; then
  CHOICE=$(zenity --list --title="Phoenix Dependency Locker" --width=520 --height=320 \
    --column="Action" \
    "List Locked Packages" \
    "Add Package to Lock" \
    "Remove Package from Lock" \
    "Apply Hold" \
    "Release Hold")
  case "$CHOICE" in
    "List Locked Packages")
      list_locks | zenity --text-info --title="Locked Packages" --width=520 --height=320 ;;
    "Add Package to Lock")
      PKG=$(zenity --entry --title="Add Package" --text="Package name:")
      [ -n "$PKG" ] && echo "$PKG" >> "$LOCKFILE" ;;
    "Remove Package from Lock")
      PKG=$(list_locks | zenity --list --title="Remove Package" --width=520 --height=320 --column="Package")
      [ -n "$PKG" ] && grep -v "^$PKG$" "$LOCKFILE" > "$LOCKFILE.tmp" && mv "$LOCKFILE.tmp" "$LOCKFILE" ;;
    "Apply Hold") apply_hold ;;
    "Release Hold") apply_unhold ;;
  esac
  exit 0
fi

case "${1:-}" in
  list) list_locks ;;
  add) echo "$2" >> "$LOCKFILE" ;;
  remove) grep -v "^$2$" "$LOCKFILE" > "$LOCKFILE.tmp" && mv "$LOCKFILE.tmp" "$LOCKFILE" ;;
  hold) apply_hold ;;
  unhold) apply_unhold ;;
  *) echo "Usage: phoenix-dependency-lock.sh {list|add <pkg>|remove <pkg>|hold|unhold}" ;;
esac
