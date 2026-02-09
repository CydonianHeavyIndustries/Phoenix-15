#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/app"
PY="$APP/venv/bin/python"

if [ ! -f "$APP/scripts/portable_launcher.py" ]; then
  echo "Portable launcher missing at $APP/scripts/portable_launcher.py"
  exit 1
fi

if [ ! -x "$PY" ]; then
  echo "Python venv not found at $APP/venv."
  echo "Run portable/linux/setup_venv.sh or install Python 3.11+."
  exit 1
fi

cd "$APP"
"$PY" "$APP/scripts/portable_launcher.py"
