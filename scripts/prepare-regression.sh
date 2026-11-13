#!/usr/bin/env bash
# prepare-regression.sh: put sellos_test.localhost in a known state for a clickthrough regression.
#
#   scripts/prepare-regression.sh
#
# It refuses to run while the SellOS build loop, a SellOS gate run or a SellOS Cypress run is going,
# because it wipes the test site. BuildOS runs beside it (SOS-SETUP-20). It builds the front end, then
# takes the bench gate lock (~/iespl-baseline/bench-gate-lock.sh) only for the restore and the migrate,
# never for the browser session that follows. It restores the clean baseline over sellos_test.localhost, clears the cache, builds the
# front end, migrates, runs prepare_clean_site and seed_regression_data, checks that the site answers at
# /sellos, and prints the URL and the six test users. It never starts or stops a server. The SellOS
# server must already be running on port 8004, pinned to the site:
#   cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004
# docs/regression/README.md says how a milestone is run.
set -euo pipefail
# shellcheck source=lib/sellos_server.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/sellos_server.sh"

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
if pgrep -f "sellos/scripts/(run-tests|build-loop)\.sh|run-ui-tests sellos" >/dev/null 2>&1; then
  echo "The SellOS build loop, a SellOS gate run or a SellOS Cypress run is in progress. Wait for it to end, then run this again." >&2
  pgrep -fl "sellos/scripts/(run-tests|build-loop)\.sh|run-ui-tests sellos" >&2 || true
  exit 3
fi
GATE_LOCK_HELPER="${SELLOS_GATE_LOCK_HELPER:-$BASELINE_DIR/bench-gate-lock.sh}"
if [ ! -f "$GATE_LOCK_HELPER" ]; then
  echo "The bench gate lock helper is missing at $GATE_LOCK_HELPER (SOS-SETUP-20)." >&2
  exit 3
fi
# shellcheck source=/dev/null
source "$GATE_LOCK_HELPER"
if [ ! -f "$BASELINE" ]; then
  echo "No clean baseline at $BASELINE. Create it with scripts/make-baseline.sh." >&2
  exit 3
fi
cd "$BENCH_DIR"
[ -d "sites/$SITE" ] || { echo "Site $SITE does not exist. Run scripts/make-baseline.sh --create." >&2; exit 3; }
# The same port rule and two part preflight as the gate (scripts/lib/sellos_server.sh): port 8004
# from the site's config or exit 2, and a server that answers ping and is SellOS or exit 3. This
# script never starts or stops a server.
sellos_require_port "$BENCH_DIR" "$SITE"
sellos_preflight "$SITE" "$PORT"

echo "--- Building the web app ---"
(
  cd "apps/$APP/frontend"
  if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
    npm ci --no-audit --no-fund
  fi
  npm run build
)

echo "--- Bench gate lock (restore and migrate only) ---"
bench_gate_acquire "SellOS prepare-regression" "${SELLOS_GATE_LOCK_MAX_WAIT:-5400}"
echo "Bench gate lock wait: ${BENCH_GATE_WAITED}s"

# SOS-SETUP-36: every table is dropped first, because a dump resets only the tables it holds.
echo "--- Restoring the clean baseline over $SITE (every table) ---"
bash "apps/$APP/scripts/lib/restore_baseline.sh" "$SITE" "$BASELINE"

echo "--- Migrating $SITE ---"
bench --site "$SITE" migrate
bench --site "$SITE" clear-cache
bench_gate_release

echo "--- Preparing the clean site and seeding the regression data ---"
bench --site "$SITE" execute "$APP.tests.ui_fixtures.prepare_clean_site"
# SOS-SETUP-36: the seed starts from a clean site, or this stops with exit 3 naming the table.
bash "apps/$APP/scripts/lib/check_clean_site.sh" "$SITE"
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
