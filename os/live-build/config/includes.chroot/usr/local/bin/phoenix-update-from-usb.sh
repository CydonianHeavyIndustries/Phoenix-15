#!/bin/sh
set -e

DEST_DIR="/opt/phoenix/app"
BACKUP_ROOT="/opt/phoenix/backups"
TMP_DIR="$(mktemp -d /tmp/phoenix-update.XXXXXX)"

cleanup() {
  rm -rf "$TMP_DIR" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! command -v zenity >/dev/null 2>&1; then
  echo "Zenity not available. Provide a zip path manually:"
  echo "Example: unzip /path/to/update.zip -d /tmp/update && rsync -a --delete /tmp/update/ /opt/phoenix/app/"
  exit 1
fi

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

zenity --info --title="Phoenix Update" --text="Update applied successfully."
