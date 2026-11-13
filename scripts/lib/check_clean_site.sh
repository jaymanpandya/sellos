#!/usr/bin/env bash
# check_clean_site.sh: refuse a test site that holds rows a clean company site never has (SOS-SETUP-36).
#
#   scripts/lib/check_clean_site.sh <site>      run from the bench folder, after prepare_test_site.sh
#
# The gate runs it after every restore and prepare, and prepare-regression.sh before it seeds. A clean
# company site, freshly restored, migrated and prepared, has no row in any of the tables below: they
# are made only by the control site (Tenant, Provisioning Job), by support access (Support Grant,
# Support Access Log) or by a person's consent (Consent Record). A row there means the restore did not
# reset the site, which is how the 13 November 2026 backend run failed (docs/STOPS.md, gate hole).
#
# Exit 0 when every table is empty. Exit 3, an environment problem that the loop never repairs, when a
# table holds rows (each is named with its row count) or cannot be read. Pipeline Stage and Plan are
# reset by the restore too but not checked here, because migrating seeds them.
set -euo pipefail
SITE="${1:?usage: check_clean_site.sh <site>}"
TABLES=("Consent Record" "Provisioning Job" "Support Access Log" "Support Grant" "Tenant")

SQL=""
for t in "${TABLES[@]}"; do
  [ -z "$SQL" ] || SQL="$SQL UNION ALL "
  SQL="${SQL}SELECT 'tab$t', COUNT(*) FROM \`tab$t\`"
done
if ! COUNTS="$(bench --site "$SITE" mariadb -N -e "$SQL" 2>&1)"; then
  echo "TEST SITE NOT CLEAN: could not count the rows of $SITE's tables: $COUNTS" >&2
  exit 3
fi

DIRTY=0
while IFS=$'\t' read -r table rows; do
  [ -n "$table" ] || continue
  if [ "$rows" != "0" ]; then
    echo "TEST SITE NOT CLEAN: $table on $SITE holds $rows rows after the restore." >&2
    DIRTY=1
  fi
done <<<"$COUNTS"
if [ "$DIRTY" -ne 0 ]; then
  echo "The baseline restore did not reset $SITE. This is an environment problem, never repaired by a task." >&2
  exit 3
fi
echo "Test site $SITE is clean: no rows in ${#TABLES[@]} checked tables."
