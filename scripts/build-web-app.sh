#!/usr/bin/env bash
# build-web-app.sh: build the SellOS web app, the one way the gate and every CI job build it (SOS-SETUP-33).
#
#   scripts/build-web-app.sh              npm ci, then npm run build (CI)
#   scripts/build-web-app.sh --if-stale   npm ci only when node_modules is older than package-lock.json (the gate)
#
# Run it from anywhere; it builds the frontend/ next to this script, so in CI's bench it builds the
# bench copy of the app (bench get-app clones only tracked files, and the built page is not tracked).
set -euo pipefail
FRONTEND="$(cd "$(dirname "${BASH_SOURCE[0]}")/../frontend" && pwd)"
cd "$FRONTEND"
if [ "${1:-}" = "--if-stale" ] && [ -f node_modules/.package-lock.json ] && ! [ package-lock.json -nt node_modules/.package-lock.json ]; then
  echo "node_modules is up to date with package-lock.json; skipping npm ci."
else
  npm ci --no-audit --no-fund
fi
npm run build
