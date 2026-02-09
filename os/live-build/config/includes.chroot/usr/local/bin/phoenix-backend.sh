#!/bin/sh
set -e

APP_ROOT="/opt/phoenix/app"
EXT_ROOT="/phoenix-data/Bjorgsun-26/app"

if [ -d "$EXT_ROOT/server" ]; then
  APP_ROOT="$EXT_ROOT"
fi

cd "$APP_ROOT"
exec /usr/bin/python3 "$APP_ROOT/server/server.py"
