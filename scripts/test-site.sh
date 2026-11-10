#!/usr/bin/env bash
# test-site.sh: make a company test site from nothing, and clean it up (SOS-P0-11).
#
#   scripts/test-site.sh up <id>    # create sellos_tenant_<id>.localhost, install SellOS, seed a test admin
#   scripts/test-site.sh down <id>  # drop the site and its database
#   scripts/test-site.sh run <id>   # up, then down even when up fails; exit 4 past the agreed time (180 s)
#
# <id> is [a-z0-9]+. The site is made only through sellos.provisioning.tenant_sites (the MariaDB
# provisioner account, never root; the password comes only from get_provisioner_password()). Exit 2 for a
# bad id, 3 when the password cannot be found, 4 when `run` is over its agreed time.
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
TENANT_PY="${SELLOS_TENANT_PYTHON:-$BENCH_DIR/env/bin/python}"

usage() {
  echo "usage: scripts/test-site.sh up <id> | down <id> | run <id>   (<id> is [a-z0-9]+)" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
case "$1" in up | down | run) ;; *) usage ;; esac
if ! [[ "$2" =~ ^[a-z0-9]+$ ]]; then
  echo "Refusing tenant id '$2': only lower case letters and digits, [a-z0-9]+." >&2
  exit 2
fi

export SELLOS_BENCH_DIR="$BENCH_DIR"
exec "$TENANT_PY" -m sellos.provisioning.site_script "$@"
