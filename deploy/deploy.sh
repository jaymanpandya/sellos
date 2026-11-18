#!/usr/bin/env bash
# deploy.sh: deploy a tagged release to staging (SOS-P0-08).
#
#   deploy/deploy.sh <tag> [--dry-run]
#
# <tag> looks like v1.2.3. --dry-run prints every step, each on a line that starts with "+ ", and
# reaches no server. A real run needs SELLOS_STAGING_HOST (user@host). Running it for real on
# staging is SOS-P0-08D (AMP Labs), never the build loop's. See docs/DEPLOYMENT.md.
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
PY="${SELLOS_DEPLOY_PYTHON:-$BENCH_DIR/env/bin/python}"
exec "$PY" -m sellos.provisioning.deploy deploy "$@"
