#!/usr/bin/env bash
# tenant-site.sh: create, drop, list and probe tenant sites on the local bench (SOS-SETUP-22).
#
#   scripts/tenant-site.sh create <id>   # sellos_tenant_<id>.localhost, database sellos_tenant_<id>
#   scripts/tenant-site.sh drop <id>
#   scripts/tenant-site.sh list
#   scripts/tenant-site.sh probe         # create, then drop, sellos_tenant_probe.localhost
#
# <id> is [a-z0-9]+ and nothing else; any other name exits 2 before anything runs. Sites are made
# and dropped with the MariaDB provisioner account (--db-root-username from SELLOS_DB_PROVISIONER_USER,
# default sellos_provisioner). The password comes from sellos.provisioning.credentials
# (SELLOS_DB_PROVISIONER_PASSWORD, else the macOS Keychain item sellos_provisioner). It is never
# printed and never on a command line: sellos.provisioning.tenant_sites hands it to Frappe's own
# command through the child process environment. Exit 3 when the password cannot be found.
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
# The Python that can import sellos: the bench's own.
TENANT_PY="${SELLOS_TENANT_PYTHON:-$BENCH_DIR/env/bin/python}"

usage() {
  echo "usage: scripts/tenant-site.sh create <id> | drop <id> | list | probe   (<id> is [a-z0-9]+)" >&2
  exit 2
}

case "${1:-}" in
  create | drop)
    [ "$#" -eq 2 ] || usage
    if ! [[ "$2" =~ ^[a-z0-9]+$ ]]; then
      echo "Refusing tenant id '$2': only lower case letters and digits, [a-z0-9]+." >&2
      exit 2
    fi
    ;;
  list | probe) [ "$#" -eq 1 ] || usage ;;
  *) usage ;;
esac

export SELLOS_BENCH_DIR="$BENCH_DIR"
exec "$TENANT_PY" -m sellos.provisioning.tenant_sites "$@"
