#!/usr/bin/env bash
# resume-loop.sh — lift a regression pause made by scripts/pause-loop.sh (SOS-SETUP-19).
# Removes the pause file. It does not start the loop: start it again with scripts/build-loop.sh.
set -euo pipefail

PAUSE_FILE="${SELLOS_PAUSE_FILE:-/tmp/sellos-loop.pause}"
rm -f "$PAUSE_FILE"
echo "SellOS loop resumed: $PAUSE_FILE removed. Start the loop with scripts/build-loop.sh."
