#!/bin/sh
set -e

APP_ROOT="/opt/phoenix/app"
EXT_ROOT="/phoenix-data/Bjorgsun-26/app"

if [ -d "$EXT_ROOT/server" ]; then
  APP_ROOT="$EXT_ROOT"
fi

. /usr/local/bin/phoenix-hw-balance.sh backend || true

cd "$APP_ROOT"
if command -v taskset >/dev/null 2>&1 && [ -n "$PHX_CPUSET" ]; then
  exec taskset -c "$PHX_CPUSET" /usr/bin/python3 "$APP_ROOT/server/server.py"
fi
exec /usr/bin/python3 "$APP_ROOT/server/server.py"
