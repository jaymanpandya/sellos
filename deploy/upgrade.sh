#!/usr/bin/env bash
# upgrade.sh: rolling upgrade, one site at a time, stopping at the first failure (SOS-P0-08).
#
#   deploy/upgrade.sh [--dry-run] [--backup] (--all-sites | --site SITE ...)
#
# Run it from the bench's own Python (SELLOS_DEPLOY_PYTHON, default the bench's env/bin/python).
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
PY="${SELLOS_DEPLOY_PYTHON:-$BENCH_DIR/env/bin/python}"
exec "$PY" -m sellos.provisioning.deploy upgrade "$@"
