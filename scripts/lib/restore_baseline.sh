#!/usr/bin/env bash
# restore_baseline.sh: put a saved baseline back over a test site, every table included (SOS-SETUP-36).
#
#   scripts/lib/restore_baseline.sh <site> <baseline.sql.gz>      run from the bench folder
#
# A dump drops and recreates only the tables it holds. A table made after the dump was saved (a new
# DocType) is not in it, so loading the dump alone left that table and its rows in place. On
# 13 November 2026 the 4 November baseline lacked seven tables (Consent Record, Pipeline Stage, Plan,
# Provisioning Job, Support Access Log, Support Grant, Tenant), and a Support Grant and Consent Records
# an agent had seeded survived every gate restore into the backend suite (docs/STOPS.md, gate hole).
# So every table, sequence and view in the site's database is dropped first, then the dump is loaded,
# then the caches are cleared. The migrate that follows (scripts/lib/prepare_test_site.sh) makes the
# tables the dump lacks, empty.
#
# It wipes the site, so only the gate's test site and the tests' own tenant sites are accepted.
set -euo pipefail
SITE="${1:?usage: restore_baseline.sh <site> <baseline.sql.gz>}"
BASELINE="${2:?usage: restore_baseline.sh <site> <baseline.sql.gz>}"

if ! [[ "$SITE" =~ ^(sellos_test(\.localhost)?|sellos_tenant_[a-z0-9]+\.localhost)$ ]]; then
  echo "Refusing to wipe site '$SITE'. Only sellos_test.localhost and sellos_tenant_<id>.localhost." >&2
  exit 2
fi
if [ ! -f "$BASELINE" ]; then
  echo "No baseline at $BASELINE." >&2
  exit 3
fi

# One statement per object, from the site's own database (DATABASE() is the site's, from its config).
# What bench prints on a failure goes to the log, as it did before the wipe was added.
LIST_STATUS=0
DROPS="$(bench --site "$SITE" mariadb -N -e "SELECT CONCAT(IF(table_type = 'VIEW', 'DROP VIEW IF EXISTS ', 'DROP TABLE IF EXISTS '), '\`', REPLACE(table_name, '\`', '\`\`'), '\`;') FROM information_schema.tables WHERE table_schema = DATABASE()")" || LIST_STATUS=$?
if [ "$LIST_STATUS" -ne 0 ]; then
  printf '%s\n' "$DROPS"
  echo "Could not list the tables of $SITE (exit $LIST_STATUS). Nothing was dropped." >&2
  exit "$LIST_STATUS"
fi
{
  echo "SET FOREIGN_KEY_CHECKS=0;"
  printf '%s\n' "$DROPS"
  echo "SET FOREIGN_KEY_CHECKS=1;"
} | bench --site "$SITE" mariadb
LEFT="$(bench --site "$SITE" mariadb -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()")"
if [ "$LEFT" != "0" ]; then
  echo "The wipe of $SITE left $LEFT tables. Not restoring over them." >&2
  exit 1
fi
echo "Dropped every table of $SITE ($(printf '%s\n' "$DROPS" | grep -c . || true) objects)."

gunzip -c "$BASELINE" | bench --site "$SITE" mariadb
bench --site "$SITE" clear-cache
bench --site "$SITE" clear-website-cache
