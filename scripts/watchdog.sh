#!/usr/bin/env bash
# watchdog.sh — checks every 2 minutes whether build-loop.sh is alive.
# If it's not, relaunches it and sends a Telegram alert so a silent
# death doesn't sit unnoticed for hours.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_INTERVAL=120

while true; do
  if ! pgrep -f "build-loop.sh" > /dev/null; then
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS watchdog: loop was not running. Relaunching it now." || true
    cd "$SCRIPT_DIR/.."
    nohup "$SCRIPT_DIR/build-loop.sh" > loop.log 2>&1 &
    sleep 5
  fi
  sleep "$CHECK_INTERVAL"
done
