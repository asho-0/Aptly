#!/bin/zsh
set -eu

LOG_FILE="/tmp/aptly-cloudflared.log"

if [[ ! -f "$LOG_FILE" ]]; then
  echo "Tunnel log not found: $LOG_FILE" >&2
  exit 1
fi

grep -Eo 'https://[a-z0-9.-]+\.trycloudflare\.com' "$LOG_FILE" | tail -n 1
