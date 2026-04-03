#!/bin/zsh
set -eu

LOG_FILE="/tmp/aptly-cloudflared.log"

mkdir -p "$(dirname "$LOG_FILE")"
exec /opt/homebrew/bin/cloudflared tunnel --url http://127.0.0.1:8080 --no-autoupdate 2>&1 | tee "$LOG_FILE"
