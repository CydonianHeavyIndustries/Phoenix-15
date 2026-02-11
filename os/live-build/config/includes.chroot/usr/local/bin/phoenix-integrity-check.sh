#!/bin/sh
set -e

DEST_DIR="/opt/phoenix/app"
MANIFEST="$DEST_DIR/.phoenix.manifest.sha256"

show() {
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="Phoenix Integrity Check" --width=520 --text="$1"
    return 0
  fi
  echo "$1"
}

if [ ! -f "$MANIFEST" ]; then
  show "No manifest found. Run update or rebuild to generate it."
  exit 1
fi

cd "$DEST_DIR"
if sha256sum -c "$MANIFEST" >/tmp/phoenix-integrity.log 2>&1; then
  show "Integrity check passed."
  exit 0
fi

if command -v zenity >/dev/null 2>&1; then
  zenity --error --title="Phoenix Integrity Check" --width=520 --text="Integrity check failed. See /tmp/phoenix-integrity.log"
else
  cat /tmp/phoenix-integrity.log
fi
exit 1
