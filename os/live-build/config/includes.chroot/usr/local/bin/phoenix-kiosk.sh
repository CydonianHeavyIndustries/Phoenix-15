#!/bin/sh
set -e

export BJORGSUN_UI_HOST="${BJORGSUN_UI_HOST:-127.0.0.1}"
export BJORGSUN_UI_PORT="${BJORGSUN_UI_PORT:-56795}"
URL="http://${BJORGSUN_UI_HOST}:${BJORGSUN_UI_PORT}/"

for i in $(seq 1 60); do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if command -v firefox-esr >/dev/null 2>&1; then
  exec /usr/bin/firefox-esr --kiosk "$URL"
fi
if command -v firefox >/dev/null 2>&1; then
  exec /usr/bin/firefox --kiosk "$URL"
fi

exec /usr/bin/chromium \
  --kiosk \
  --app="$URL" \
  --no-first-run \
  --disable-translate \
  --disable-session-crashed-bubble \
  --autoplay-policy=no-user-gesture-required
