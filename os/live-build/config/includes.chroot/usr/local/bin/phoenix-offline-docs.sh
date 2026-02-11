#!/bin/sh
set -e

DOC_PATH="/opt/phoenix/docs/offline/index.html"

if [ ! -f "$DOC_PATH" ]; then
  echo "Offline docs not found: $DOC_PATH"
  exit 1
fi

if command -v firefox-esr >/dev/null 2>&1; then
  exec firefox-esr "file://$DOC_PATH"
fi
if command -v firefox >/dev/null 2>&1; then
  exec firefox "file://$DOC_PATH"
fi
if command -v xdg-open >/dev/null 2>&1; then
  exec xdg-open "$DOC_PATH"
fi

echo "Open this file in a browser: $DOC_PATH"
