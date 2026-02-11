#!/bin/sh
set -e

usage() {
  cat <<'USAGE'
Phoenix App Downloader

Usage:
  phoenix-app-download.sh apt <package>
  phoenix-app-download.sh flatpak <package>
  phoenix-app-download.sh search <query>
  phoenix-app-download.sh web <query>

Examples:
  phoenix-app-download.sh apt vlc
  phoenix-app-download.sh flatpak org.videolan.VLC
  phoenix-app-download.sh search vlc
  phoenix-app-download.sh web "vlc linux"
USAGE
}

ensure_flathub() {
  if command -v flatpak >/dev/null 2>&1; then
    if ! flatpak remotes --columns=name 2>/dev/null | grep -q "^flathub$"; then
      flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
    fi
  fi
}

cmd="$1"
shift || true

case "$cmd" in
  apt)
    pkg="$1"
    if [ -z "$pkg" ]; then usage; exit 1; fi
    sudo apt-get update
    sudo apt-get install -y "$pkg"
    ;;
  flatpak)
    pkg="$1"
    if [ -z "$pkg" ]; then usage; exit 1; fi
    ensure_flathub
    flatpak install -y flathub "$pkg"
    ;;
  search)
    query="$*"
    if [ -z "$query" ]; then usage; exit 1; fi
    echo "APT search:"
    apt-cache search "$query" | head -n 25
    if command -v flatpak >/dev/null 2>&1; then
      ensure_flathub
      echo ""
      echo "Flatpak search:"
      flatpak search "$query" | head -n 25
    fi
    ;;
  web)
    query="$*"
    if [ -z "$query" ]; then usage; exit 1; fi
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "https://www.google.com/search?q=$(printf "%s" "$query" | sed 's/ /+/g')"
    else
      echo "xdg-open not available."
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
