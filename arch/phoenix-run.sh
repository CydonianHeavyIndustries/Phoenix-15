#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/opt/Bjorgsun-26"
APP_DIR="$ROOT_DIR/app"
UI_URL="http://127.0.0.1:1326"
PHX_DATA_LABEL="${PHX_DATA_LABEL:-PHOENIX_DATA}"
DATA_MOUNT="/phoenix-data"
DATA_ROOT="$DATA_MOUNT/bjorgsun"

cd "$APP_DIR"

if ! mountpoint -q "$DATA_MOUNT"; then
  dev="$(lsblk -rpo NAME,LABEL | awk -v label="$PHX_DATA_LABEL" '$2==label {print $1; exit}')"
  if [ -n "$dev" ]; then
    mkdir -p "$DATA_MOUNT"
    mount "$dev" "$DATA_MOUNT" || true
  fi
fi

if mountpoint -q "$DATA_MOUNT"; then
  mkdir -p "$DATA_ROOT/app-data" "$DATA_ROOT/server-data" "$DATA_ROOT/logs" "$DATA_ROOT/session_logs"

  if [ ! -L "$APP_DIR/data" ]; then
    if [ -d "$APP_DIR/data" ]; then
      rsync -a "$APP_DIR/data/" "$DATA_ROOT/app-data/" || true
      rm -rf "$APP_DIR/data"
    fi
    ln -s "$DATA_ROOT/app-data" "$APP_DIR/data"
  fi

  if [ ! -L "$APP_DIR/server/data" ]; then
    if [ -d "$APP_DIR/server/data" ]; then
      rsync -a "$APP_DIR/server/data/" "$DATA_ROOT/server-data/" || true
      rm -rf "$APP_DIR/server/data"
    fi
    ln -s "$DATA_ROOT/server-data" "$APP_DIR/server/data"
  fi

  export MEMORY_PATH="$DATA_ROOT/app-data/memory.json"
  export HANDOFF_PATH="$DATA_ROOT/app-data/Bjorgsun26_memory_handoff.json"
  export VISUAL_MEMORY_PATH="$DATA_ROOT/app-data/visual_memory.json"
  export SESSION_LOG_DIR="$DATA_ROOT/session_logs"
fi

echo "[phoenix] Starting backend..."
./venv/bin/python server/server.py > "$ROOT_DIR/phoenix_server.log" 2>&1 &
SERVER_PID=$!

echo "[phoenix] Waiting for backend..."
for i in {1..30}; do
  if curl -s "$UI_URL/ping" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[phoenix] Launching UI..."
chromium --app="$UI_URL" --start-maximized --no-first-run --no-default-browser-check &

wait $SERVER_PID
