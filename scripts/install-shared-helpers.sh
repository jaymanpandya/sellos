#!/usr/bin/env bash
# install-shared-helpers.sh: install the bench helpers this repository keeps the canonical copy of
# (SOS-SETUP-21). Today that is the bench gate lock, scripts/shared/bench-gate-lock.sh, which goes to
# ~/iespl-baseline/bench-gate-lock.sh, outside both repositories, where every gate sources it.
#
#   scripts/install-shared-helpers.sh
#
# SELLOS_BASELINE_DIR overrides ~/iespl-baseline (for the tests).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE_DIR="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}"
SOURCE="$REPO_DIR/scripts/shared/bench-gate-lock.sh"
TARGET="$BASELINE_DIR/bench-gate-lock.sh"

mkdir -p "$BASELINE_DIR"
# Copy beside the target and rename, so a gate sourcing it never reads half a file.
TMP="$(mktemp "$BASELINE_DIR/.bench-gate-lock.XXXXXX")"
cp "$SOURCE" "$TMP"
chmod 755 "$TMP"
mv -f "$TMP" "$TARGET"
echo "Installed $TARGET from $SOURCE"
