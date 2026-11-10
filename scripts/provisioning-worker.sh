#!/usr/bin/env bash
# provisioning-worker.sh: run the SellOS provisioning worker (SOS-P1-02) on the control site.
#
#   scripts/provisioning-worker.sh <control site>          # work until stopped (Ctrl-C)
#   scripts/provisioning-worker.sh <control site> --once   # do one job, or say there is none
#
# It is its own process, never the web server. It makes company sites only through
# sellos.provisioning.tenant_sites (the MariaDB provisioner account, never root). The password is
# never printed and never on a command line. It does not start or touch any server.
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
TENANT_PY="${SELLOS_TENANT_PYTHON:-$BENCH_DIR/env/bin/python}"

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: scripts/provisioning-worker.sh <control site> [--once]" >&2
  exit 2
fi

export SELLOS_BENCH_DIR="$BENCH_DIR"
cd "$BENCH_DIR/sites"
exec "$TENANT_PY" -m sellos.provisioning.worker "$@"
