#!/bin/sh
set -e

OUT="/var/log/phoenix_issue_summary.log"
mkdir -p /var/log

{
  echo "Phoenix Issue Summary"
  echo "====================="
  echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)"
  echo ""
  echo "Failed services:"
  systemctl --failed || true
  echo ""
  echo "Recent errors (journalctl -p err..alert -b):"
  journalctl -p err..alert -b --no-pager || true
} > "$OUT"

if command -v zenity >/dev/null 2>&1; then
  zenity --text-info --title="Phoenix Issue Summary" --width=800 --height=500 --filename="$OUT"
else
  cat "$OUT"
fi
