#!/bin/sh
set -e

LOG_PATH="/var/log/phoenix_llm_install.log"
MARKER="/var/lib/phoenix/llm_installed"
MODEL="${OLLAMA_BOOT_MODEL:-llama3.2:1b}"
BOOTSTRAP="${PHX_LLM_BOOTSTRAP:-1}"

log() {
  TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)
  echo "[$TS] $*" | tee -a "$LOG_PATH" >/dev/null 2>&1 || true
}

if [ "$BOOTSTRAP" = "0" ]; then
  log "bootstrap disabled"
  exit 0
fi

if [ -f "$MARKER" ]; then
  log "marker exists, skipping"
  exit 0
fi

if ! command -v ping >/dev/null 2>&1; then
  log "ping not available, continuing without network check"
else
  if ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    log "network unavailable"
    exit 1
  fi
fi

if ! command -v ollama >/dev/null 2>&1; then
  log "installing ollama"
  curl -fsSL https://ollama.com/install.sh | sh
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl enable --now ollama >/dev/null 2>&1 || true
fi

if command -v ollama >/dev/null 2>&1; then
  log "pulling model: $MODEL"
  ollama pull "$MODEL"
fi

mkdir -p /var/lib/phoenix
touch "$MARKER"
log "llm install complete"
