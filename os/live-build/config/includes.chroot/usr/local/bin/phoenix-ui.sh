#!/bin/sh
set -e

APP_ROOT="/opt/phoenix/app"
EXT_ROOT="/phoenix-data/Bjorgsun-26/app"

if [ -d "$EXT_ROOT/ui" ]; then
  APP_ROOT="$EXT_ROOT"
fi

export BJORGSUN_UI_DIST="${APP_ROOT}/ui/scifiaihud/build"
export BJORGSUN_UI_HOST="${BJORGSUN_UI_HOST:-127.0.0.1}"
export BJORGSUN_UI_PORT="${BJORGSUN_UI_PORT:-56795}"
export BJORGSUN_UI_WEBVIEW="${BJORGSUN_UI_WEBVIEW:-0}"
export BJORGSUN_UI_HEADLESS="${BJORGSUN_UI_HEADLESS:-1}"

. /usr/local/bin/phoenix-hw-balance.sh ui || true

cd "$APP_ROOT"
if command -v taskset >/dev/null 2>&1 && [ -n "$PHX_CPUSET" ]; then
  exec taskset -c "$PHX_CPUSET" /usr/bin/python3 "$APP_ROOT/scripts/start_ui.py" --force
fi
exec /usr/bin/python3 "$APP_ROOT/scripts/start_ui.py" --force
