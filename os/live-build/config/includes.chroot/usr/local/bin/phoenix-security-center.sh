#!/bin/sh
set -e

QUARANTINE="/opt/phoenix/quarantine"
LOG_DIR="/opt/phoenix/logs"
LOG_FILE="$LOG_DIR/security.log"

mkdir -p "$QUARANTINE" "$LOG_DIR"

notify() {
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="Phoenix Security Center" --width=520 --text="$1" >/dev/null 2>&1 || true
  else
    printf "%s\n" "$1"
  fi
}

error() {
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="Phoenix Security Center" --width=520 --text="$1" >/dev/null 2>&1 || true
  else
    printf "ERROR: %s\n" "$1"
  fi
}

log() {
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)" "$1" >> "$LOG_FILE"
}

ensure_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    error "Missing required command: $1"
    exit 1
  fi
}

firewall_status() {
  ensure_cmd ufw
  ufw status verbose || true
}

firewall_enable() {
  ensure_cmd ufw
  ufw --force reset >/dev/null 2>&1 || true
  ufw default deny incoming >/dev/null 2>&1 || true
  ufw default allow outgoing >/dev/null 2>&1 || true
  ufw --force enable >/dev/null 2>&1 || true
  log "Firewall enabled (ufw)."
  notify "Firewall enabled."
}

firewall_disable() {
  ensure_cmd ufw
  ufw --force disable >/dev/null 2>&1 || true
  log "Firewall disabled (ufw)."
  notify "Firewall disabled."
}

antivirus_update() {
  ensure_cmd freshclam
  freshclam 2>&1 | tee -a "$LOG_FILE" || true
  log "Antivirus definitions updated."
  notify "Antivirus definitions updated."
}

scan_quick() {
  ensure_cmd clamscan
  log "Quick scan started."
  clamscan -r --move="$QUARANTINE" /home 2>&1 | tee -a "$LOG_FILE" || true
  log "Quick scan finished."
  notify "Quick scan finished. Quarantine: $QUARANTINE"
}

scan_full() {
  ensure_cmd clamscan
  log "Full scan started."
  clamscan -r --move="$QUARANTINE" / 2>&1 | tee -a "$LOG_FILE" || true
  log "Full scan finished."
  notify "Full scan finished. Quarantine: $QUARANTINE"
}

live_protection_on() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now clamav-freshclam clamav-daemon >/dev/null 2>&1 || true
    log "Live protection enabled (clamav-daemon)."
    notify "Live protection enabled."
  else
    error "systemctl not available; cannot enable services."
  fi
}

live_protection_off() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now clamav-daemon clamav-freshclam >/dev/null 2>&1 || true
    log "Live protection disabled (clamav-daemon)."
    notify "Live protection disabled."
  else
    error "systemctl not available; cannot disable services."
  fi
}

open_quarantine() {
  if command -v thunar >/dev/null 2>&1; then
    thunar "$QUARANTINE" >/dev/null 2>&1 &
  else
    notify "Quarantine path: $QUARANTINE"
  fi
}

security_report() {
  ensure_cmd ufw
  ensure_cmd clamscan
  fw="$(ufw status verbose 2>&1 | head -n 6)"
  av="$(clamscan --version 2>&1 | head -n 1)"
  log "Security report requested."
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="Phoenix Security Report" --width=620 --text="Firewall:\n$fw\n\nAntivirus:\n$av\n\nQuarantine:\n$QUARANTINE\n\nLog:\n$LOG_FILE" >/dev/null 2>&1 || true
  else
    printf "Firewall:\n%s\n\nAntivirus:\n%s\n\nQuarantine:\n%s\n\nLog:\n%s\n" "$fw" "$av" "$QUARANTINE" "$LOG_FILE"
  fi
}

if ! command -v zenity >/dev/null 2>&1; then
  error "Zenity not available. Run with one of: status|fw-on|fw-off|av-update|scan-quick|scan-full|live-on|live-off|quarantine|report"
  exit 1
fi

CHOICE=$(zenity --list --title="Phoenix Security Center" --width=520 --height=420 \
  --column="Action" \
  "Firewall Status" \
  "Enable Firewall" \
  "Disable Firewall" \
  "Antivirus Update" \
  "Quick Scan (Home)" \
  "Full Scan (All)" \
  "Enable Live Protection" \
  "Disable Live Protection" \
  "Open Quarantine" \
  "Security Report")

case "$CHOICE" in
  "Firewall Status") firewall_status | zenity --text-info --title="Firewall Status" --width=620 --height=420 --filename=- ;;
  "Enable Firewall") firewall_enable ;;
  "Disable Firewall") firewall_disable ;;
  "Antivirus Update") antivirus_update ;;
  "Quick Scan (Home)") scan_quick ;;
  "Full Scan (All)") scan_full ;;
  "Enable Live Protection") live_protection_on ;;
  "Disable Live Protection") live_protection_off ;;
  "Open Quarantine") open_quarantine ;;
  "Security Report") security_report ;;
esac
