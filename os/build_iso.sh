#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="phoenix-15-os"

if command -v docker >/dev/null 2>&1; then
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker build -t "$IMAGE" -f "$ROOT/os/docker/Dockerfile" "$ROOT"
  fi
  docker run --rm -e PHX_ROOT=/work -v "$ROOT:/work" "$IMAGE" /work/os/docker/build.sh
else
  export PHX_ROOT="$ROOT"
  bash "$ROOT/os/docker/build.sh"
fi

echo "ISO output: $ROOT/os/out/phoenix-15.iso"
