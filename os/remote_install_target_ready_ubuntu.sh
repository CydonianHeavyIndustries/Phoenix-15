#!/usr/bin/env bash
set -euo pipefail

PORT="${PHX_READY_PORT:-16326}"
USER_NAME="${PHX_TARGET_USER:-${USER:-ubuntu}}"
WORK_DIR="${PHX_READY_DIR:-/tmp/phoenix-ready}"

echo "[phoenix] Preparing Ubuntu target..."
sudo apt-get update
sudo apt-get install -y openssh-server python3
sudo systemctl enable --now ssh

IP="$(hostname -I | awk '{print $1}')"
if [ -z "$IP" ]; then
  echo "[phoenix] Could not detect LAN IP."
  exit 1
fi

mkdir -p "$WORK_DIR"
cat > "$WORK_DIR/ready.json" <<EOF
{
  "project": "Phoenix-15",
  "user": "$USER_NAME",
  "ip": "$IP",
  "port": $PORT,
  "status": "ready"
}
EOF

cat > "$WORK_DIR/index.html" <<EOF
<html><body><h2>Phoenix-15 target ready</h2><p>Use /ready.json</p></body></html>
EOF

echo "[phoenix] Target is ready."
echo "[phoenix] SSH user: $USER_NAME"
echo "[phoenix] Target IP: $IP"
echo "[phoenix] Beacon URL: http://$IP:$PORT/ready.json"
echo "[phoenix] Keep this running. Press Ctrl+C to stop."

cd "$WORK_DIR"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
