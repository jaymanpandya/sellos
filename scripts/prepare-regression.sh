#!/usr/bin/env bash
# prepare-regression.sh: put sellos_test.localhost in a known state for a clickthrough regression.
#
#   scripts/prepare-regression.sh
#
# It refuses to run while the build loop, a gate run or a BuildOS gate is running, because it wipes the
# test site. Then it restores the clean baseline over sellos_test.localhost, clears the cache, builds the
# front end, migrates, runs prepare_clean_site and seed_regression_data, checks that the site answers at
# /sellos, and prints the URL and the six test users. It never starts or stops the bench: bench start
# must already be running and serving the site. docs/regression/README.md says how a milestone is run.
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
APP="${SELLOS_APP:-sellos}"
SITE="${SELLOS_TEST_SITE:-sellos_test.localhost}"
BASELINE_DIR="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}"
BASELINE="$BASELINE_DIR/sellos_test_clean.sql.gz"

if ! [[ "$SITE" =~ ^sellos_test(\.localhost)?$ ]]; then
  echo "Refusing to use site '$SITE'. This restores a baseline over it. Use sellos_test.localhost." >&2
  exit 2
fi

echo "--- Preflight ---"
if pgrep -f "scripts/(run-tests|build-loop)\.sh|run-ui-tests" >/dev/null 2>&1; then
  echo "The build loop, a gate run (SellOS or BuildOS) or a Cypress run is in progress. Wait for it to end, then run this again." >&2
  pgrep -fl "scripts/(run-tests|build-loop)\.sh|run-ui-tests" >&2 || true
  exit 3
fi
if [ ! -f "$BASELINE" ]; then
  echo "No clean baseline at $BASELINE. Create it with scripts/make-baseline.sh." >&2
  exit 3
fi
cd "$BENCH_DIR"
[ -d "sites/$SITE" ] || { echo "Site $SITE does not exist. Run scripts/make-baseline.sh --create." >&2; exit 3; }
PORT="$(python3 -c "import json;print(json.load(open('sites/common_site_config.json')).get('webserver_port', 8000))")"
if ! curl -s -o /dev/null --max-time 10 "http://$SITE:$PORT/api/method/ping"; then
  echo "The bench is not serving $SITE on port $PORT. Start it yourself with bench start. This script never does." >&2
  exit 3
fi

echo "--- Restoring the clean baseline over $SITE ---"
gunzip -c "$BASELINE" | bench --site "$SITE" mariadb
bench --site "$SITE" clear-cache
bench --site "$SITE" clear-website-cache

echo "--- Building the web app ---"
(
  cd "apps/$APP/frontend"
  if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
    npm ci --no-audit --no-fund
  fi
  npm run build
)

echo "--- Migrating $SITE ---"
bench --site "$SITE" migrate
bench --site "$SITE" clear-cache

echo "--- Preparing the clean site and seeding the regression data ---"
bench --site "$SITE" execute "$APP.tests.ui_fixtures.prepare_clean_site"
bench --site "$SITE" execute "$APP.tests.ui_fixtures.seed_regression_data"
bench --site "$SITE" clear-cache

URL="http://$SITE:$PORT/sellos"
echo "--- Checking that $URL answers ---"
CODE="$(curl -s -o /dev/null --max-time 20 -w '%{http_code}' "$URL" || true)"
case "$CODE" in
  2*|3*) echo "$URL answered $CODE." ;;
  *) echo "$URL answered '$CODE', not a 2xx or 3xx. The site is not ready." >&2; exit 4 ;;
esac

echo
echo "READY: $URL"
echo "Sign in with the password below (test site only). The six test users:"
bench --site "$SITE" execute "$APP.testing.users.users_for_smoke" 2>/dev/null | python3 -c "
import json, sys
text = sys.stdin.read().strip()
rows = json.loads(text.splitlines()[-1]) if text else []
for row in rows:
    print('  ' + row['email'], '|', ', '.join(row['roles']) or 'no SellOS role')
if rows:
    print('Password: ' + rows[0]['password'])
"
echo "Regression agents: regression_agent_two@example.com, regression_agent_three@example.com (same password)."
