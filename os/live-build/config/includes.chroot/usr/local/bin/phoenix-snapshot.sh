#!/bin/sh
set -e

BASE="/var/lib/phoenix/snapshots"
mkdir -p "$BASE"

timestamp() {
  date -u +"%Y%m%dT%H%M%SZ" 2>/dev/null || date +"%Y%m%d_%H%M%S"
}

list_snaps() {
  ls -1 "$BASE" 2>/dev/null | grep -E '\.tar\.gz$' || true
}

create_snap() {
  NAME="${1:-snapshot-$(timestamp)}"
  OUT="$BASE/$NAME.tar.gz"
  tar -czf "$OUT" \
    --exclude="logs" \
    --exclude="*.log" \
    /etc/phoenix \
    /opt/phoenix/app \
    /var/lib/phoenix \
    2>/dev/null || true
  echo "$OUT"
}

restore_snap() {
  SNAP="$1"
  if [ -z "$SNAP" ] || [ ! -f "$SNAP" ]; then
    echo "Snapshot not found: $SNAP"
    exit 1
  fi
  rm -rf /opt/phoenix/app || true
  mkdir -p /opt/phoenix
  tar -xzf "$SNAP" -C / 2>/dev/null || true
  echo "Restored: $SNAP"
}

if command -v zenity >/dev/null 2>&1; then
  ACTION=$(zenity --list --title="Phoenix Snapshots" --width=520 --height=340 \
    --column="Action" \
    "Create Snapshot" \
    "Restore Snapshot" \
    "List Snapshots")
  case "$ACTION" in
    "Create Snapshot")
      NAME=$(zenity --entry --title="Snapshot Name" --text="Name (optional):")
      OUT=$(create_snap "$NAME")
      zenity --info --title="Snapshot Created" --text="Saved: $OUT"
      ;;
    "Restore Snapshot")
      CHOICE=$(list_snaps | zenity --list --title="Choose Snapshot" --width=600 --height=400 --column="Snapshot")
      if [ -n "$CHOICE" ]; then
        restore_snap "$BASE/$CHOICE"
        zenity --info --title="Snapshot Restored" --text="Restored: $CHOICE"
      fi
      ;;
    "List Snapshots")
      list_snaps | zenity --text-info --title="Snapshots" --width=600 --height=400
      ;;
  esac
  exit 0
fi

case "${1:-}" in
  list) list_snaps ;;
  create) create_snap "$2" ;;
  restore) restore_snap "$2" ;;
  *)
    echo "Usage: phoenix-snapshot.sh {list|create [name]|restore <file>}"
    ;;
esac
