#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${PHX_REPO_URL:-https://github.com/CydonianHeavyIndustries/Phoenix-15.git}"
BRANCH="${PHX_BRANCH:-main}"
TARGET_DIR="${PHX_TARGET_DIR:-$HOME/Phoenix-15}"
MIN_FREE_GB="${PHX_MIN_FREE_GB:-6}"
FORCE_RESET=0

usage() {
  cat <<'USAGE'
Phoenix-15 ISO workspace bootstrap

Usage:
  bash os/bootstrap_iso_workspace.sh [--force] [--target <path>] [--branch <name>] [--repo <url>]

Options:
  --force           Remove an existing non-git target directory first.
  --target <path>   Clone/update target path (default: ~/Phoenix-15)
  --branch <name>   Branch to use (default: main)
  --repo <url>      Repository URL

This performs a low-footprint sparse checkout suitable for ISO builds.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force)
      FORCE_RESET=1
      ;;
    --target)
      TARGET_DIR="${2:-}"
      shift
      ;;
    --branch)
      BRANCH="${2:-}"
      shift
      ;;
    --repo)
      REPO_URL="${2:-}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[phoenix-os] Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

if ! command -v git >/dev/null 2>&1; then
  echo "[phoenix-os] git is required."
  exit 1
fi

PARENT_DIR="$(dirname "$TARGET_DIR")"
mkdir -p "$PARENT_DIR"

WRITE_TEST="$PARENT_DIR/.phx_write_test.$$"
if ! ( : > "$WRITE_TEST" ) 2>/dev/null; then
  echo "[phoenix-os] Cannot write to $PARENT_DIR."
  echo "[phoenix-os] Fix permissions or choose a writable target with --target."
  exit 1
fi
rm -f "$WRITE_TEST" 2>/dev/null || true

FREE_KB="$(df -Pk "$PARENT_DIR" | awk 'NR==2 {print $4}')"
MIN_KB="$((MIN_FREE_GB * 1024 * 1024))"
if [ -n "$FREE_KB" ] && [ "$FREE_KB" -lt "$MIN_KB" ]; then
  echo "[phoenix-os] Not enough free space in $PARENT_DIR."
  echo "[phoenix-os] Free: ${FREE_KB}KB, required: ${MIN_KB}KB (${MIN_FREE_GB}GB)."
  exit 1
fi

if [ -e "$TARGET_DIR" ] && [ ! -d "$TARGET_DIR/.git" ]; then
  if [ "$FORCE_RESET" -eq 1 ]; then
    rm -rf "$TARGET_DIR"
  else
    echo "[phoenix-os] Target exists and is not a git repo: $TARGET_DIR"
    echo "[phoenix-os] Re-run with --force to replace it."
    exit 1
  fi
fi

if [ ! -d "$TARGET_DIR/.git" ]; then
  git clone --filter=blob:none --no-checkout --single-branch --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
fi

git -C "$TARGET_DIR" remote set-url origin "$REPO_URL" >/dev/null 2>&1 || true
git -C "$TARGET_DIR" fetch --depth 1 origin "$BRANCH"
git -C "$TARGET_DIR" checkout -B "$BRANCH" "origin/$BRANCH"

git -C "$TARGET_DIR" sparse-checkout init --no-cone
cat > "$TARGET_DIR/.git/info/sparse-checkout" <<'EOF'
/os/
/app/
/portable/
/install_choices.json
!/app/audio_profile_app/frontend/node_modules/
!/app/ui/src/
!/app/ui/scifiaihud/src/
!/app/data/users/
!/app/data/memory_exports/
!/app/data/session_logs/
!/app/logs/
EOF

git -C "$TARGET_DIR" sparse-checkout reapply

echo "[phoenix-os] Workspace ready: $TARGET_DIR"
echo "[phoenix-os] Next step:"
echo "  bash \"$TARGET_DIR/os/build_iso_ubuntu.sh\""
