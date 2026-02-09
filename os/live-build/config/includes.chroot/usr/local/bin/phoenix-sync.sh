#!/bin/sh
set -e

UPDATE_DIR="${PHX_UPDATE_DIR:-/phoenix-data/phoenix_update}"
DEST_DIR="/opt/phoenix/app"

if [ -d "$UPDATE_DIR" ]; then
  rsync -a --delete "$UPDATE_DIR/" "$DEST_DIR/"
fi
