#!/bin/sh
set -e

SERVER_ROOT="${PHX_SERVER_ROOT:-$HOME/PhoenixGameServers}"
STEAMCMD_DIR="${HOME}/.local/share/steamcmd"
STEAMCMD_BIN="${STEAMCMD_DIR}/steamcmd.sh"
TEMPLATE_FILE="${SERVER_ROOT}/server-setup.txt"
PROFILE_FILE="/usr/local/share/phoenix/server_profiles.txt"

ensure_dirs() {
  mkdir -p "$SERVER_ROOT"
  mkdir -p "$(dirname "$STEAMCMD_DIR")"
}

ensure_steamcmd() {
  if [ -x "$STEAMCMD_BIN" ]; then
    return 0
  fi
  ensure_dirs
  tmp="/tmp/steamcmd_linux.tar.gz"
  curl -L -o "$tmp" "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
  tar -xzf "$tmp" -C "$STEAMCMD_DIR"
  rm -f "$tmp"
}

write_template() {
  ensure_dirs
  if [ ! -f "$TEMPLATE_FILE" ]; then
    cat >"$TEMPLATE_FILE" <<'EOF'
Phoenix-15 Game Server Quick Start

1) Install SteamCMD (if needed)
   Run: /usr/local/bin/phoenix-game-server.sh and choose "Install/Update SteamCMD"

2) Install a dedicated server
   Example (replace <APP_ID>, <USER>, <PASS>):
   ~/.local/share/steamcmd/steamcmd.sh +login <USER> <PASS> +force_install_dir "$HOME/PhoenixGameServers/YourServer" +app_update <APP_ID> validate +quit

3) Run the server
   Each game provides its own start script inside the install folder.
   Example:
   cd "$HOME/PhoenixGameServers/YourServer"
   ./start_server.sh

4) Notes
   - Keep server files inside PhoenixGameServers for easy backups.
   - Open required ports in your router if hosting public servers.
EOF
  fi
}

open_folder() {
  ensure_dirs
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$SERVER_ROOT" >/dev/null 2>&1 &
    return 0
  fi
  return 1
}

pick_terminal() {
  if command -v x-terminal-emulator >/dev/null 2>&1; then
    echo "x-terminal-emulator"
    return 0
  fi
  if command -v xfce4-terminal >/dev/null 2>&1; then
    echo "xfce4-terminal"
    return 0
  fi
  if command -v gnome-terminal >/dev/null 2>&1; then
    echo "gnome-terminal"
    return 0
  fi
  return 1
}

run_in_terminal() {
  cmd="$1"
  term="$(pick_terminal || true)"
  if [ -n "$term" ]; then
    if [ "$term" = "xfce4-terminal" ]; then
      "$term" --hold -e "sh -c '$cmd'" >/dev/null 2>&1 &
    elif [ "$term" = "gnome-terminal" ]; then
      "$term" -- bash -lc "$cmd; echo; read -p 'Press enter to close...'" >/dev/null 2>&1 &
    else
      "$term" -e "sh -c '$cmd'" >/dev/null 2>&1 &
    fi
  else
    sh -c "$cmd"
  fi
}

install_server_interactive() {
  ensure_steamcmd
  appid=$(zenity --entry --title="SteamCMD Server Install" --text="Enter Steam App ID (dedicated server):" --width=420)
  if [ -z "$appid" ]; then
    return 0
  fi
  dir=$(zenity --entry --title="Install Folder" --text="Folder name under $SERVER_ROOT:" --width=420)
  if [ -z "$dir" ]; then
    return 0
  fi
  login=$(zenity --entry --title="Steam Login" --text="Steam username (leave blank for anonymous if supported):" --width=420)
  pass=""
  if [ -n "$login" ] && [ "$login" != "anonymous" ]; then
    pass=$(zenity --entry --title="Steam Password" --hide-text --text="Steam password (leave blank if not needed):" --width=420)
  else
    login="anonymous"
  fi
  target="${SERVER_ROOT}/${dir}"
  mkdir -p "$target"
  cmd="\"$STEAMCMD_BIN\" +force_install_dir \"$target\" +login $login $pass +app_update $appid validate +quit"
  run_in_terminal "$cmd"
}

update_server_interactive() {
  ensure_steamcmd
  target=$(zenity --file-selection --directory --title="Select Server Folder" --filename="$SERVER_ROOT/")
  if [ -z "$target" ]; then
    return 0
  fi
  appid=$(zenity --entry --title="SteamCMD Update" --text="Enter Steam App ID (dedicated server):" --width=420)
  if [ -z "$appid" ]; then
    return 0
  fi
  login=$(zenity --entry --title="Steam Login" --text="Steam username (leave blank for anonymous if supported):" --width=420)
  pass=""
  if [ -n "$login" ] && [ "$login" != "anonymous" ]; then
    pass=$(zenity --entry --title="Steam Password" --hide-text --text="Steam password (leave blank if not needed):" --width=420)
  else
    login="anonymous"
  fi
  cmd="\"$STEAMCMD_BIN\" +force_install_dir \"$target\" +login $login $pass +app_update $appid validate +quit"
  run_in_terminal "$cmd"
}

show_info() {
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="Phoenix Game Server" --width=520 --text="$1"
    return 0
  fi
  echo "$1"
}

ensure_profiles() {
  if [ -f "$PROFILE_FILE" ]; then
    return 0
  fi
  mkdir -p "$(dirname "$PROFILE_FILE")"
  cat >"$PROFILE_FILE" <<'EOF'
Valheim Dedicated Server|896660|anonymous|Start: ./start_server.sh
Team Fortress 2 Dedicated Server|232250|anonymous|Start: ./srcds_run -game tf +map ctf_2fort
Project Zomboid Dedicated Server|380870|anonymous|Start: ./start-server.sh
Terraria Dedicated Server|105600|anonymous|Start: ./start-server.sh
Steam Dedicated Server (Custom App ID)|CUSTOM|anonymous|Start: see game docs
Minecraft (Manual Install)|MANUAL||Start: java -jar server.jar
EOF
}

install_profile() {
  ensure_profiles
  choice=$(zenity --list --title="Server Profiles" --width=640 --height=360 \
    --column="Profile" --column="App ID" --column="Login" --column="Notes" \
    $(awk -F'|' '{print $1, $2, $3, $4}' "$PROFILE_FILE"))
  if [ -z "$choice" ]; then
    return 0
  fi
  name="$(echo "$choice" | awk '{print $1}')"
  appid="$(grep -F "$name|" "$PROFILE_FILE" | head -n1 | cut -d'|' -f2)"
  login="$(grep -F "$name|" "$PROFILE_FILE" | head -n1 | cut -d'|' -f3)"
  note="$(grep -F "$name|" "$PROFILE_FILE" | head -n1 | cut -d'|' -f4)"

  if [ "$appid" = "MANUAL" ]; then
    show_info "Manual server setup.\n$note\nFolder: $SERVER_ROOT"
    open_folder || true
    return 0
  fi
  if [ "$appid" = "CUSTOM" ]; then
    appid=$(zenity --entry --title="Custom App ID" --text="Enter Steam App ID:" --width=420)
    if [ -z "$appid" ]; then
      return 0
    fi
  fi
  ensure_steamcmd
  dir=$(zenity --entry --title="Install Folder" --text="Folder name under $SERVER_ROOT:" --width=420)
  if [ -z "$dir" ]; then
    return 0
  fi
  login_prompt=$login
  if [ -z "$login_prompt" ]; then
    login_prompt="anonymous"
  fi
  if [ "$login_prompt" = "anonymous" ]; then
    user="anonymous"
    pass=""
  else
    user=$(zenity --entry --title="Steam Login" --text="Steam username:" --width=420)
    if [ -z "$user" ]; then
      return 0
    fi
    pass=$(zenity --entry --title="Steam Password" --hide-text --text="Steam password (leave blank if not needed):" --width=420)
  fi
  target="${SERVER_ROOT}/${dir}"
  mkdir -p "$target"
  cmd="\"$STEAMCMD_BIN\" +force_install_dir \"$target\" +login $user $pass +app_update $appid validate +quit"
  run_in_terminal "$cmd"
  show_info "Installed $name.\n$note"
}

if ! command -v zenity >/dev/null 2>&1; then
  write_template
  echo "Phoenix Game Server ready."
  echo "Server folder: $SERVER_ROOT"
  echo "Template: $TEMPLATE_FILE"
  exit 0
fi

CHOICE=$(zenity --list --title="Phoenix Game Server" --width=520 --height=360 \
  --column="Action" \
  "Server Profiles (Quick Install)" \
  "Install Server (SteamCMD)" \
  "Update Server (SteamCMD)" \
  "Install/Update SteamCMD" \
  "Open Server Folder" \
  "Create Setup Template" \
  "Run SteamCMD (advanced)")

case "$CHOICE" in
  "Server Profiles (Quick Install)")
    install_profile
    ;;
  "Install Server (SteamCMD)")
    install_server_interactive
    ;;
  "Update Server (SteamCMD)")
    update_server_interactive
    ;;
  "Install/Update SteamCMD")
    ensure_steamcmd
    show_info "SteamCMD is ready.\nPath: $STEAMCMD_BIN"
    ;;
  "Open Server Folder")
    if ! open_folder; then
      show_info "Server folder: $SERVER_ROOT"
    fi
    ;;
  "Create Setup Template")
    write_template
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$TEMPLATE_FILE" >/dev/null 2>&1 &
    fi
    ;;
  "Run SteamCMD (advanced)")
    ensure_steamcmd
    if command -v x-terminal-emulator >/dev/null 2>&1; then
      x-terminal-emulator -e "$STEAMCMD_BIN" &
    else
      show_info "SteamCMD ready at:\n$STEAMCMD_BIN"
    fi
    ;;
esac
