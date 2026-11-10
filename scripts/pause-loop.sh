#!/usr/bin/env bash
# pause-loop.sh — pause the SellOS build loop for a scheduled regression (SOS-SETUP-19).
# Creates the pause file. Before picking each task the loop checks for it, and if it exists the loop
# picks nothing, notifies "Paused for regression" and stops. A task already running finishes first.
# Undo with scripts/resume-loop.sh.
set -euo pipefail

PAUSE_FILE="${SELLOS_PAUSE_FILE:-/tmp/sellos-loop.pause}"
date -u +"%Y-%m-%dT%H:%M:%SZ paused for regression" >"$PAUSE_FILE"
echo "SellOS loop paused: $PAUSE_FILE exists. Run scripts/resume-loop.sh to resume."
