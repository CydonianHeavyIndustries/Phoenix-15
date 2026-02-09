#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/app"
PYBASE="${PYTHON:-python3}"
PY="$APP/venv/bin/python"

if [ -x "$PY" ]; then
  echo "venv already exists at $APP/venv"
  exit 0
fi

cd "$APP"
"$PYBASE" -m venv "$APP/venv"
PY="$APP/venv/bin/python"

REQ="$APP/requirements-linux.txt"
if [ ! -f "$REQ" ]; then
  REQ="$APP/requirements.txt"
fi

"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r "$REQ"

echo "Setup complete. Run portable/linux/run_phoenix.sh"
