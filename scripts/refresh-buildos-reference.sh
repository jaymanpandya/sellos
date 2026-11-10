#!/usr/bin/env bash
# refresh-buildos-reference.sh: make a read only reference copy of the BuildOS source (SOS-SETUP-21).
#
#   scripts/refresh-buildos-reference.sh
#
# The SellOS loop agent may read BuildOS only in this copy, ~/iespl-baseline/buildos-reference, with
# ls, cat, grep and find. It never reads, lists or runs anything under apps/buildos, where the BuildOS
# loop is working at the same time. The copy is the BuildOS working tree as it is, without .git,
# node_modules, the built front end (buildos/public/frontend, buildos/www/buildos.html), logs and *.log,
# __pycache__ and *.pyc. It is made writable, synced, then made read only again (chmod -R a-w).
# The build loop runs this once at its start. It prints the BuildOS commit it copied.
#
# SELLOS_BUILDOS_SOURCE and SELLOS_BUILDOS_REFERENCE override the two folders (for the tests).
set -euo pipefail

SOURCE="${SELLOS_BUILDOS_SOURCE:-${SELLOS_BENCH_DIR:-$HOME/iespl-bench}/apps/buildos}"
REFERENCE="${SELLOS_BUILDOS_REFERENCE:-$HOME/iespl-baseline/buildos-reference}"

if [ ! -d "$SOURCE" ]; then
  echo "BuildOS source not found at $SOURCE. The reference copy was not refreshed." >&2
  exit 3
fi

mkdir -p "$(dirname "$REFERENCE")"
if [ -d "$REFERENCE" ]; then
  chmod -R u+w "$REFERENCE"
else
  mkdir "$REFERENCE"
fi

rsync -a --delete --delete-excluded \
  --exclude=.git \
  --exclude=node_modules \
  --exclude=/buildos/public/frontend \
  --exclude=/buildos/www/buildos.html \
  --exclude=logs \
  --exclude='*.log' \
  --exclude=__pycache__ \
  --exclude='*.pyc' \
  "$SOURCE/" "$REFERENCE/"

chmod -R a-w "$REFERENCE"

COMMIT="$(git -C "$SOURCE" rev-parse HEAD 2>/dev/null || echo unknown)"
SUBJECT="$(git -C "$SOURCE" log -1 --format=%s 2>/dev/null || true)"
DIRTY=""
if [ "$COMMIT" != unknown ] && [ -n "$(git -C "$SOURCE" status --porcelain 2>/dev/null)" ]; then
  DIRTY=" plus uncommitted changes in the working tree"
fi
echo "BuildOS reference: copied commit $COMMIT${SUBJECT:+ ($SUBJECT)}$DIRTY from $SOURCE to $REFERENCE (read only)."
