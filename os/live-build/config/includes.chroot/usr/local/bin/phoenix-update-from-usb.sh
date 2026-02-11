#!/bin/sh
set -e

DEST_DIR="/opt/phoenix/app"
BACKUP_ROOT="/opt/phoenix/backups"
BACKUP_LIMIT=5
TMP_DIR="$(mktemp -d /tmp/phoenix-update.XXXXXX)"

cleanup() {
  rm -rf "$TMP_DIR" >/dev/null 2>&1 || true
}
trap cleanup EXIT

show_info() {
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="Phoenix Update" --width=520 --text="$1"
    return 0
  fi
  echo "$1"
}

regenerate_manifest() {
  if command -v sha256sum >/dev/null 2>&1; then
    find "$DEST_DIR" -type f -print0 | sort -z | xargs -0 sha256sum >"$DEST_DIR/.phoenix.manifest.sha256" || true
  fi
}

prune_backups() {
  if [ ! -d "$BACKUP_ROOT" ]; then
    return 0
  fi
  count=$(ls -1d "$BACKUP_ROOT"/phoenix-update-* 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -le "$BACKUP_LIMIT" ]; then
    return 0
  fi
  remove=$((count - BACKUP_LIMIT))
  ls -1d "$BACKUP_ROOT"/phoenix-update-* 2>/dev/null | sort | head -n "$remove" | xargs -r rm -rf
}

rollback_latest() {
  if [ ! -d "$BACKUP_ROOT" ]; then
    show_info "No backups found."
    exit 0
  fi
  latest=$(ls -1d "$BACKUP_ROOT"/phoenix-update-* 2>/dev/null | sort | tail -n 1)
  if [ -z "$latest" ]; then
    show_info "No backups found."
    exit 0
  fi
  if ! rsync -a --delete "$latest/" "$DEST_DIR/"; then
    show_info "Rollback failed."
    exit 1
  fi
  regenerate_manifest
  show_info "Rollback complete."
}

if ! command -v zenity >/dev/null 2>&1; then
  echo "Zenity not available. Provide a zip path manually:"
  echo "Example: unzip /path/to/update.zip -d /tmp/update && rsync -a --delete /tmp/update/ /opt/phoenix/app/"
  exit 1
fi

ACTION=$(zenity --list --title="Phoenix Update" --width=520 --height=300 \
  --column="Action" \
  "Apply update from ZIP" \
  "Rollback last update" \
  "Open backups folder")

case "$ACTION" in
  "Rollback last update")
    rollback_latest
    exit 0
    ;;
  "Open backups folder")
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$BACKUP_ROOT" >/dev/null 2>&1 &
    else
      show_info "Backups stored at: $BACKUP_ROOT"
    fi
    exit 0
    ;;
esac

ZIP_PATH=$(zenity --file-selection --title="Select Phoenix Update ZIP" --file-filter="Zip files (*.zip) | *.zip")
if [ -z "$ZIP_PATH" ]; then
  exit 0
fi

if ! command -v unzip >/dev/null 2>&1; then
  zenity --error --title="Phoenix Update" --text="unzip is not installed. Please install it and retry."
  exit 1
fi

mkdir -p "$TMP_DIR/extract"
if ! unzip -q "$ZIP_PATH" -d "$TMP_DIR/extract"; then
  zenity --error --title="Phoenix Update" --text="Failed to extract ZIP."
  exit 1
fi

SOURCE_DIR=""
if [ -d "$TMP_DIR/extract/app" ]; then
  SOURCE_DIR="$TMP_DIR/extract/app"
elif [ -d "$TMP_DIR/extract/Phoenix-15/app" ]; then
  SOURCE_DIR="$TMP_DIR/extract/Phoenix-15/app"
elif [ -d "$TMP_DIR/extract/Bjorgsun-26/app" ]; then
  SOURCE_DIR="$TMP_DIR/extract/Bjorgsun-26/app"
else
  SOURCE_DIR="$TMP_DIR/extract"
fi

mkdir -p "$BACKUP_ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/phoenix-update-$STAMP"
mkdir -p "$BACKUP_DIR"

rsync -a --delete "$DEST_DIR/" "$BACKUP_DIR/" || true
if ! rsync -a --delete "$SOURCE_DIR/" "$DEST_DIR/"; then
  zenity --error --title="Phoenix Update" --text="Update failed. Restoring backup."
  rsync -a --delete "$BACKUP_DIR/" "$DEST_DIR/" || true
  exit 1
fi

regenerate_manifest
prune_backups

zenity --info --title="Phoenix Update" --text="Update applied successfully."
