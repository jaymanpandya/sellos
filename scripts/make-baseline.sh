#!/usr/bin/env bash
# make-baseline.sh: create the clean test site, its saved snapshot, and the Semgrep tooling.
#
#   scripts/make-baseline.sh --create   create sellos_test.localhost first (asks for the MariaDB root password)
#   scripts/make-baseline.sh            (re)save the snapshot of the existing site
#
# Run it again whenever the clean starting data should change on purpose. The gate restores this
# snapshot over the test site before every run, so nothing a test leaves behind survives.
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
APP="${SELLOS_APP:-sellos}"
SITE="${SELLOS_TEST_SITE:-sellos_test.localhost}"
BASELINE_DIR="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}"

if ! [[ "$SITE" =~ ^sellos_test(\.localhost)?$ ]]; then
  echo "Refusing to use site '$SITE'." >&2
  exit 2
fi
mkdir -p "$BASELINE_DIR"
cd "$BENCH_DIR"

if [ "${1:-}" = "--create" ] && [ ! -d "sites/$SITE" ]; then
  echo "bench will ask for the MariaDB root password."
  bench new-site "$SITE" --admin-password "${SELLOS_TEST_ADMIN_PASSWORD:-admin}" --install-app "$APP"
  bench --site "$SITE" set-config allow_tests true
  # SellOS runs only on port 8004. run-ui-tests builds Cypress's base URL from this, and the gate
  # refuses any other port. Serve it with: cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004
  bench --site "$SITE" set-config -p webserver_port 8004
fi
[ -d "sites/$SITE" ] || { echo "Site $SITE does not exist. Run with --create." >&2; exit 1; }

bench --site "$SITE" migrate
# The baseline is the clean migrated install only. prepare_clean_site (the company site state and the
# role users) runs in scripts/run-tests.sh on every run, so it is never frozen into the snapshot.
bench --site "$SITE" clear-cache
bench --site "$SITE" backup
LATEST="$(ls -t "sites/$SITE/private/backups/"*-database.sql.gz | head -1)"
cp "$LATEST" "$BASELINE_DIR/sellos_test_clean.sql.gz"
echo "Baseline saved: $BASELINE_DIR/sellos_test_clean.sql.gz"

if [ ! -d "$BASELINE_DIR/semgrep-rules/rules" ]; then
  git clone --depth 1 https://github.com/frappe/semgrep-rules.git "$BASELINE_DIR/semgrep-rules"
fi
if [ ! -x "$BASELINE_DIR/semgrep-venv/bin/semgrep" ]; then
  python3 -m venv "$BASELINE_DIR/semgrep-venv"
  "$BASELINE_DIR/semgrep-venv/bin/pip" install --quiet semgrep
fi
echo "Semgrep and the Frappe rules are ready."
