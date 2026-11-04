#!/usr/bin/env bash
# run-tests.sh: the real test gate for SellOS. Copied from BuildOS's gate, with the holes closed.
#
# Order: preflight, lint and Semgrep, the task guards, put the clean baseline back, build the web
# app, migrate, prepare_clean_site (code, every run), the test files the task changed first (a failure stops the gate at once), the
# whole backend suite, then the whole Cypress suite. A failed UI spec is rerun once, alone. The
# gate passes only if every rerun passes, each spec that needed a rerun is logged as FLAKY, and a
# spec that is FLAKY three times is a failure until it is fixed. More than 5 failed specs, or
# failures that cannot be identified, fail at once.
#
# The build loop sets SELLOS_TASK_ID, SELLOS_BASE_SHA and SELLOS_TASK_BLOCK_FILE so the task
# guards run. A human running the gate by hand leaves them unset and the guards are skipped.
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
APP="${SELLOS_APP:-sellos}"
SITE="${SELLOS_TEST_SITE:-sellos_test.localhost}"
BASELINE_DIR="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}"
BASELINE="$BASELINE_DIR/sellos_test_clean.sql.gz"
MAX_RERUN=5
FLAKY_LIMIT=3

# The baseline is restored over this site, wiping it. It must never be a site that holds real work.
if ! [[ "$SITE" =~ ^sellos_test(\.localhost)?$ ]]; then
  echo "Refusing to use site '$SITE'. The gate restores a baseline over it. Use sellos_test.localhost." >&2
  exit 2
fi

export CYPRESS_site="$SITE"
if [ -n "${SELLOS_TEST_ADMIN_PASSWORD:-}" ]; then
  export CYPRESS_adminPassword="$SELLOS_TEST_ADMIN_PASSWORD"
fi

LOG_DIR="/tmp/sellos-test-logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/run-$STAMP.log"
UI_LOG="$LOG_DIR/ui-$STAMP.log"
FLAKY_LOG="$BASELINE_DIR/sellos-flaky.log"
rm -f "$LOG_DIR/latest.log"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BENCH_DIR"

set +e
{
set -e
echo "=== SellOS test run: $(date) ==="

echo "--- Preflight ---"
# The BuildOS gate uses the same bench. Two gates at once restore databases and clear the cache
# under each other, so wait for it rather than corrupt both runs.
if pgrep -f "buildos/scripts/(run-tests|build-loop)\.sh" >/dev/null 2>&1; then
  echo "A BuildOS gate or loop is running on this bench. Wait for it, then run this again." >&2
  exit 3
fi
PORT="$(python3 -c "import json;print(json.load(open('sites/common_site_config.json')).get('webserver_port', 8000))")"
if ! curl -s -o /dev/null --max-time 10 "http://$SITE:$PORT/api/method/ping"; then
  echo "The bench is not serving $SITE on port $PORT. Start it with bench start, and make sure $SITE exists." >&2
  echo "Cypress needs the site at its own address. Create it once with scripts/make-baseline.sh --create." >&2
  exit 3
fi
# The baseline is what makes every run start from the same data. Running without it is how a test
# passes today and fails tomorrow, so it is an error unless a human says otherwise.
if [ ! -f "$BASELINE" ] && [ -z "${SELLOS_ALLOW_NO_BASELINE:-}" ]; then
  echo "No clean baseline at $BASELINE. Create it with scripts/make-baseline.sh." >&2
  echo "A human may set SELLOS_ALLOW_NO_BASELINE=reason to run without it, once." >&2
  exit 3
fi
if [ ! -x "$BASELINE_DIR/semgrep-venv/bin/semgrep" ] || [ ! -d "$BASELINE_DIR/semgrep-rules/rules" ]; then
  echo "Semgrep or the Frappe rules are missing. Run scripts/make-baseline.sh once. CI runs them on every push." >&2
  exit 3
fi

echo "--- Lint and Semgrep (the same checks CI runs) ---"
(
  cd "$REPO_DIR"
  # The first pass may rewrite files (ruff format). The second must come back clean.
  pre-commit run --all-files || pre-commit run --all-files
  "$BASELINE_DIR/semgrep-venv/bin/semgrep" --metrics=off --error --quiet \
    --config "$BASELINE_DIR/semgrep-rules/rules" --exclude node_modules --exclude cypress .
)

if [ -n "${SELLOS_TASK_ID:-}" ]; then
  echo "--- Task guards: $SELLOS_TASK_ID ---"
  (
    cd "$REPO_DIR"
    python3 scripts/check_gate_files.py "$SELLOS_BASE_SHA" "$SELLOS_TASK_BLOCK_FILE"
    python3 scripts/check_assertion_ratchet.py "$SELLOS_BASE_SHA"
    python3 scripts/check_task_evidence.py "$SELLOS_TASK_ID" "$SELLOS_BASE_SHA" "$SELLOS_TASK_BLOCK_FILE"
  )
else
  echo "--- Task guards skipped: no task is set (a hand run) ---"
fi

# every gate run starts from the same clean data: put the saved snapshot back before anything else
if [ -f "$BASELINE" ]; then
  echo "--- Restoring the clean test site baseline ---"
  gunzip -c "$BASELINE" | bench --site "$SITE" mariadb
  bench --site "$SITE" clear-cache
  bench --site "$SITE" clear-website-cache
else
  echo "--- NO BASELINE (allowed by a human): running on the existing test site data ---"
fi

echo "--- Building web app: $APP/frontend ---"
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
# The baseline is a clean migrated install. The state a provisioned company site is in, and the role
# users, are made by code on every run, so the gate exercises the same code provisioning uses.
echo "--- Preparing the clean site (code, every run) ---"
bench --site "$SITE" execute "$APP.tests.ui_fixtures.prepare_clean_site"
bench --site "$SITE" clear-cache

echo "--- Changed tests first: $APP ---"
CHANGED="$(git -C "apps/$APP" status --porcelain -uall | { grep -v -E '^(.D|D.) ' || true; } | sed -E 's/^.{2} //; s/.* -> //')"
CHANGED_PY="$(printf '%s\n' "$CHANGED" | grep -E '(^|/)test_[^/]*\.py$' || true)"
CHANGED_SPECS="$(printf '%s\n' "$CHANGED" | grep -E '^cypress/integration/.*\.cy\.js$' || true)"
# canary specs: a change under cypress/support touches every spec, so run the most sensitive ones early
if printf '%s\n' "$CHANGED" | grep -qE '^cypress/support/'; then
  echo "--- cypress/support changed, adding the canary specs ---"
  CHANGED_SPECS="$CHANGED_SPECS
cypress/integration/smoke/app_shell.cy.js
cypress/integration/crm/leads_by_role.cy.js
cypress/integration/security/phone_masking_leaks.cy.js"
fi
for f in $CHANGED_PY; do
  [ -f "apps/$APP/$f" ] || { echo "--- skipping $f: the task deleted it ---"; continue; }
  mod="$(printf '%s' "${f%.py}" | tr '/' '.')"
  echo "--- changed test module: $mod ---"
  bench --site "$SITE" run-tests --app "$APP" --module "$mod" || { echo "CHANGED TEST FAILED: $mod"; exit 1; }
done
for f in $CHANGED_SPECS; do
  [ -f "apps/$APP/$f" ] || { echo "--- skipping $f: the task deleted it ---"; continue; }
  spec="${f#cypress/integration/}"
  echo "--- changed spec: $spec ---"
  if ! bench --site "$SITE" run-ui-tests "$APP" --headless --spec "cypress/integration/$spec"; then
    echo "--- RERUN once, alone: $spec ---"
    bench --site "$SITE" clear-cache
    bench --site "$SITE" run-ui-tests "$APP" --headless --spec "cypress/integration/$spec" || { echo "CHANGED SPEC FAILED AGAIN: $spec"; exit 1; }
    echo "FLAKY (passed on rerun): $spec"
    echo "$(date +%F) $spec" >>"$FLAKY_LOG"
  fi
done

echo "--- Backend unit tests: $APP ---"
bench --site "$SITE" run-tests --app "$APP"

echo "--- UI tests: $APP ---"
set +e
bench --site "$SITE" run-ui-tests "$APP" --headless 2>&1 | tee "$UI_LOG"
UI_STATUS="${PIPESTATUS[0]}"
set -e

if [ "$UI_STATUS" -ne 0 ]; then
  FAILED_SPECS="$(awk '
/Failing: +[0-9]+/ { f=$0; gsub(/[^0-9]/, "", f); fail=f+0 }
/Spec Ran:/ { s=$0; sub(/.*Spec Ran: +/, "", s); sub(/ *│.*/, "", s); if (fail>0) print s; fail=0 }
' "$UI_LOG")"
  COUNT="$(printf '%s\n' "$FAILED_SPECS" | grep -c . || true)"
  if [ -z "$FAILED_SPECS" ] || [ "$COUNT" -gt "$MAX_RERUN" ]; then
    echo "--- UI tests failed ($COUNT specs identified), not rerunning ---"
    exit 1
  fi
  STILL_FAILING=0
  for spec in $FAILED_SPECS; do
    echo "--- RERUN once, alone: $spec ---"
    bench --site "$SITE" clear-cache
    if bench --site "$SITE" run-ui-tests "$APP" --headless --spec "cypress/integration/$spec"; then
      echo "FLAKY (passed on rerun): $spec"
      echo "$(date +%F) $spec" >>"$FLAKY_LOG"
    else
      echo "FAILED AGAIN: $spec"
      STILL_FAILING=1
    fi
  done
  [ "$STILL_FAILING" -eq 0 ] || exit 1
fi

# A spec that keeps needing a rerun is hiding a real fault. Three strikes and the gate stops.
if [ -f "$FLAKY_LOG" ]; then
  REPEAT="$(awk '{print $2}' "$FLAKY_LOG" | sort | uniq -c | awk -v n="$FLAKY_LIMIT" '$1 >= n {print $2 " (" $1 " times)"}')"
  if [ -n "$REPEAT" ]; then
    echo "--- FLAKY too often, fix these specs: $REPEAT ---"
    exit 1
  fi
fi
echo "--- GATE PASSED ---"
} 2>&1 | tee "$LOG_FILE"

STATUS="${PIPESTATUS[0]}"
ln -sf "$LOG_FILE" "$LOG_DIR/latest.log"
exit "$STATUS"
