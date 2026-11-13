#!/usr/bin/env bash
# run-tests.sh: the real test gate for SellOS. Copied from BuildOS's gate, with the holes closed.
#
# Order: new files marked intent-to-add, preflight (CI parity, a snapshot of the bench's sites and databases), lint and Semgrep, the task guards, put the clean baseline back, build the web
# app, migrate, prepare_clean_site (code, every run), the tenant template (on unless SELLOS_TENANT_TEMPLATE=off, SOS-SETUP-32), the test files the task changed first (a failure stops the gate at once), the
# whole backend suite (a module that failed on a MariaDB 1020 or deadlock is rerun once, alone, and
# a second database conflict exits 3, SOS-SETUP-25), the whole Cypress suite, then a check that no other site or database was touched and
# that no secret is in a log: the provisioner's password (SOS-SETUP-18), the Telegram values and BuildOS's credentials (SOS-SETUP-29). A failed UI spec is rerun once, alone. The
# gate passes only if every rerun passes, each spec that needed a rerun is logged as FLAKY, and a
# spec that is FLAKY three times is a failure until it is fixed. More than 5 failed specs, or
# failures that cannot be identified, fail at once. That policy lives in scripts/lib/ui_flaky.sh, and
# CI's UI job runs Cypress through the same script (SOS-SETUP-27).
#
# The build loop sets SELLOS_TASK_ID, SELLOS_BASE_SHA and SELLOS_TASK_BLOCK_FILE so the task
# guards run. A human running the gate by hand leaves them unset and the guards are skipped.
set -euo pipefail

BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
APP="${SELLOS_APP:-sellos}"
SITE="${SELLOS_TEST_SITE:-sellos_test.localhost}"
BASELINE_DIR="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}"
BASELINE="$BASELINE_DIR/sellos_test_clean.sql.gz"
# The UI rerun policy (scripts/lib/ui_flaky.sh) reads these. CI's UI job uses the same defaults.
export SELLOS_MAX_RERUN=5
export SELLOS_FLAKY_LIMIT=3

# The baseline is restored over this site, wiping it. It must never be a site that holds real work.
if ! [[ "$SITE" =~ ^sellos_test(\.localhost)?$ ]]; then
  echo "Refusing to use site '$SITE'. The gate restores a baseline over it. Use sellos_test.localhost." >&2
  exit 2
fi

export CYPRESS_site="$SITE"
if [ -n "${SELLOS_TEST_ADMIN_PASSWORD:-}" ]; then
  export CYPRESS_adminPassword="$SELLOS_TEST_ADMIN_PASSWORD"
fi

LOG_DIR="${SELLOS_LOG_DIR:-/tmp/sellos-test-logs}"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/run-$STAMP.log"
UI_LOG="$LOG_DIR/ui-$STAMP.log"
export SELLOS_FLAKY_LOG="$BASELINE_DIR/sellos-flaky.log"
rm -f "$LOG_DIR/latest.log"
# Exit 2 and 3 mean an environment problem, and the build loop never repairs, resets or Blocks a
# task for one (SOS-SETUP-14). Only the preflight's own exits, recorded by sellos_env_exit, keep a
# 2 or 3. Any other failure ends as 1, whatever status the failing command returned: under set -e
# a command's own 2 (a click usage error, say) would otherwise look like an environment problem.
export SELLOS_ENV_EXIT_FILE="$LOG_DIR/env-exit-$STAMP"
rm -f "$SELLOS_ENV_EXIT_FILE"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/sellos_server.sh
source "$REPO_DIR/scripts/lib/sellos_server.sh"
# SOS-SETUP-18: the provisioner account's values are redacted from everything the gate writes, and
# the end of the run fails if the password is in any log, the repository or a tenant site.
# shellcheck source=lib/db_secrets.sh
source "$REPO_DIR/scripts/lib/db_secrets.sh"
# SOS-SETUP-22: on a hand run the password may be only in the Keychain. Load it (never shown) so the
# redaction and the leak check below know it. Nothing fails when it is not available.
sellos_load_provisioner_password || true
GATE_START="$(date +%s)"
# Claude Code keeps the agent's session transcripts here, named after the folder it ran in.
CLAUDE_TRANSCRIPTS="$HOME/.claude/projects/$(printf '%s' "$REPO_DIR" | sed 's/[^A-Za-z0-9]/-/g')"
cd "$BENCH_DIR"

set +e
{
set -e
echo "=== SellOS test run: $(date) ==="

# CI lints and scans every file in the commit, new ones included. pre-commit --all-files and
# semgrep ci see only files git tracks, and a task's new files stay untracked until the loop
# commits them. Mark them intent-to-add so every check below sees them, without staging content.
# The loop's failure path (git add -A, salvage commit, reset --hard, clean -fd) still removes them.
(
  cd "$REPO_DIR"
  git ls-files --others --exclude-standard -z | xargs -0 git add --intent-to-add
)

echo "--- Preflight ---"
# SOS-SETUP-20: the BuildOS and SellOS loops run at the same time. Their sites do not collide (Redis
# keys are namespaced per site, bench clear-cache is per site), so nothing waits for BuildOS here.
# Only the heavy segment, from the baseline restore to the end of the Cypress run, takes the bench
# gate lock that every gate on this bench shares (~/iespl-baseline/bench-gate-lock.sh).
GATE_LOCK_HELPER="${SELLOS_GATE_LOCK_HELPER:-$BASELINE_DIR/bench-gate-lock.sh}"
if [ ! -f "$GATE_LOCK_HELPER" ]; then
  echo "The bench gate lock helper is missing at $GATE_LOCK_HELPER. It lives outside the repositories (SOS-SETUP-20)." >&2
  sellos_env_exit 3
fi
# shellcheck source=/dev/null
source "$GATE_LOCK_HELPER"
# SellOS runs only on port 8004, on its own server pinned to this site (scripts/lib/sellos_server.sh).
# The port comes from the site's config the way run-ui-tests reads it, anything else is refused
# (exit 2), and the server must prove it is SellOS, not only that it answers (exit 3). CI is not
# affected: it runs on its own machine on port 8000 and never runs this script.
sellos_require_port "$BENCH_DIR" "$SITE"
sellos_preflight "$SITE" "$PORT"
# SOS-SETUP-17: CI must build the bench this machine runs. CI's bench init once named no Frappe
# branch, got Frappe develop (no cypress/support), and every UI spec failed there while passing here.
if ! python3 "$REPO_DIR/scripts/check_ci_parity.py" "$BENCH_DIR" "$REPO_DIR/.github/workflows/ci.yml"; then
  echo "Make the local bench and .github/workflows/ci.yml agree, then run this again." >&2
  sellos_env_exit 3
fi
# SOS-SETUP-17: other apps' sites share this bench. Record every site now, and at the end fail if a
# site other than sellos_test.localhost or sellos_tenant_<id>.localhost was touched, or a tenant site
# this run made was left behind.
# SOS-SETUP-18: with the provisioner's password set it records the databases too, and an account
# that cannot list them is an environment problem (exit 3).
SITES_SNAPSHOT="$LOG_DIR/sites-$STAMP.json"
SNAPSHOT_STATUS=0
python3 "$REPO_DIR/scripts/check_site_set.py" snapshot "$BENCH_DIR" "$SITES_SNAPSHOT" || SNAPSHOT_STATUS=$?
if [ "$SNAPSHOT_STATUS" -eq 3 ]; then sellos_env_exit 3; fi
if [ "$SNAPSHOT_STATUS" -ne 0 ]; then exit 1; fi
# The baseline is what makes every run start from the same data. Running without it is how a test
# passes today and fails tomorrow, so it is an error unless a human says otherwise.
if [ ! -f "$BASELINE" ] && [ -z "${SELLOS_ALLOW_NO_BASELINE:-}" ]; then
  echo "No clean baseline at $BASELINE. Create it with scripts/make-baseline.sh." >&2
  echo "A human may set SELLOS_ALLOW_NO_BASELINE=reason to run without it, once." >&2
  sellos_env_exit 3
fi
if [ ! -x "$BASELINE_DIR/semgrep-venv/bin/semgrep" ] || [ ! -d "$BASELINE_DIR/semgrep-rules/rules" ]; then
  echo "Semgrep or the Frappe rules are missing. Run scripts/make-baseline.sh once. CI runs them on every push." >&2
  sellos_env_exit 3
fi

echo "--- Lint and Semgrep (the same checks CI runs) ---"
(
  cd "$REPO_DIR"
  # The first pass may rewrite files (ruff format). The second must come back clean.
  pre-commit run --all-files || pre-commit run --all-files
  # Exactly CI's command (.github/workflows/linter.yml), reading the same .semgrepignore.
  "$BASELINE_DIR/semgrep-venv/bin/semgrep" ci \
    --config "$BASELINE_DIR/semgrep-rules/rules" --config r/python.lang.correctness
)

# SOS-SETUP-16: the whole Cypress suite runs below, so a spec for a later task is skipped until that
# task. A skip that names no task, or a task that is Complete or is the one being finished, fails.
echo "--- Skipped specs wait for an unfinished task ---"
(
  cd "$REPO_DIR"
  python3 scripts/check_no_stale_skips.py ${SELLOS_TASK_ID:+--current "$SELLOS_TASK_ID"} TASKS.md cypress/integration
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

echo "--- Building web app: $APP/frontend ---"
(
  cd "apps/$APP/frontend"
  if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
    npm ci --no-audit --no-fund
  fi
  npm run build
)

# The heavy segment starts here and ends after the Cypress run. A wait past SELLOS_GATE_LOCK_MAX_WAIT
# (default 90 minutes) exits 3 inside the helper, recorded beforehand as an environment problem.
echo "--- Bench gate lock (restore to the end of Cypress) ---"
echo 3 >"$SELLOS_ENV_EXIT_FILE"
export BENCH_GATE_NOTIFY="$REPO_DIR/scripts/notify-telegram.sh"
bench_gate_acquire "SellOS gate${SELLOS_TASK_ID:+ $SELLOS_TASK_ID}" "${SELLOS_GATE_LOCK_MAX_WAIT:-5400}"
rm -f "$SELLOS_ENV_EXIT_FILE"
echo "Bench gate lock wait: ${BENCH_GATE_WAITED}s"

# every gate run starts from the same clean data: put the saved snapshot back before anything else
if [ -f "$BASELINE" ]; then
  echo "--- Restoring the clean test site baseline ---"
  gunzip -c "$BASELINE" | bench --site "$SITE" mariadb
  bench --site "$SITE" clear-cache
  bench --site "$SITE" clear-website-cache
else
  echo "--- NO BASELINE (allowed by a human): running on the existing test site data ---"
fi

echo "--- Migrating $SITE ---"
bench --site "$SITE" migrate
bench --site "$SITE" clear-cache
# The baseline is a clean migrated install. The state a provisioned company site is in, and the role
# users, are made by code on every run, so the gate exercises the same code provisioning uses.
echo "--- Preparing the clean site (code, every run) ---"
bench --site "$SITE" execute "$APP.tests.ui_fixtures.prepare_clean_site"
bench --site "$SITE" clear-cache

# SOS-SETUP-32: the tenant template, on by default, with CI's rule (SOS-SETUP-28). One tenant site is
# made with Frappe's full install, dumped and dropped, and every tenant site the tests make is built
# from the dump, except inside full_install(), which exactly one real provisioning test uses
# (sellos/provisioning/test_tenant_template.py checks both). Without it the integration batch took
# 669 s here against about 2 minutes on CI. SELLOS_TENANT_TEMPLATE=off turns it off for one run.
# It is made after the migrate, from the code under test, so the dump is never stale.
export SELLOS_TENANT_TEMPLATE="${SELLOS_TENANT_TEMPLATE:-on}"
TEMPLATE_SQL="$LOG_DIR/tenant-template-$STAMP.sql"
unset SELLOS_TENANT_TEMPLATE_SQL
if [ "$SELLOS_TENANT_TEMPLATE" = "off" ]; then
  echo "--- Tenant template off (SELLOS_TENANT_TEMPLATE=off): every tenant site gets the full install ---"
elif [ "$SELLOS_TENANT_TEMPLATE" != "on" ]; then
  echo "SELLOS_TENANT_TEMPLATE must be on or off, not '$SELLOS_TENANT_TEMPLATE'." >&2
  sellos_env_exit 2
elif ! sellos_provisioner_available; then
  echo "The tenant template needs the provisioner password (SOS-SETUP-22). Store it, or run with SELLOS_TENANT_TEMPLATE=off." >&2
  sellos_env_exit 3
else
  echo "--- Making the tenant template (one full install) ---"
  TEMPLATE_START="$(date +%s)"
  # A failure here is the code's: the full install of a tenant site broke, which the one real
  # provisioning test would find too.
  (cd sites && ../env/bin/python -m "$APP.tests.tenant_template" make "$TEMPLATE_SQL") \
    || { echo "TENANT TEMPLATE FAILED: the full install of a tenant site failed"; exit 1; }
  export SELLOS_TENANT_TEMPLATE_SQL="$TEMPLATE_SQL"
  echo "Tenant template made in $(($(date +%s) - TEMPLATE_START)) s"
fi

echo "--- Changed tests first: $APP ---"
REPORT_TEST_EXIT="apps/$APP/scripts/lib/report_test_exit.sh"
DB_CONFLICT="apps/$APP/scripts/lib/db_conflict.py"
DB_CONFLICT_LOG="$BASELINE_DIR/sellos-db-conflict.log"
# SOS-SETUP-25: run_backend reruns a module that failed on a MariaDB 1020 or deadlock once, alone,
# and exits 3 if the rerun hits one again (scripts/lib/db_conflict.sh).
# shellcheck source=lib/db_conflict.sh
source "$REPO_DIR/scripts/lib/db_conflict.sh"
# SOS-SETUP-27: the one rerun policy for Cypress, shared with CI's UI job.
# shellcheck source=lib/ui_flaky.sh
source "$REPO_DIR/scripts/lib/ui_flaky.sh"
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
  run_backend "$LOG_DIR/backend-$STAMP-$mod.log" --module "$mod" || { echo "CHANGED TEST FAILED: $mod"; exit 1; }
done
for f in $CHANGED_SPECS; do
  [ -f "apps/$APP/$f" ] || { echo "--- skipping $f: the task deleted it ---"; continue; }
  spec="${f#cypress/integration/}"
  echo "--- changed spec: $spec ---"
  sellos_ui_suite "$LOG_DIR/ui-$STAMP-changed-$(printf '%s' "$spec" | tr '/' '_').log" "$spec" \
    || { echo "CHANGED SPEC FAILED: $spec"; exit 1; }
done

echo "--- Backend unit tests: $APP ---"
# The runner prints one summary per batch, and the last one can say OK while an earlier one failed.
# The wrapper prints every batch and the exit code, and the exit code decides (SOS-SETUP-24).
run_backend "$LOG_DIR/backend-$STAMP-all.log" || { echo "BACKEND TESTS FAILED"; exit 1; }
rm -f "$TEMPLATE_SQL"
unset SELLOS_TENANT_TEMPLATE_SQL

echo "--- UI tests: $APP ---"
# Rerun once, alone; FLAKY on a passing rerun; three times FLAKY fails (scripts/lib/ui_flaky.sh).
sellos_ui_suite "$UI_LOG" || { echo "UI TESTS FAILED"; exit 1; }
# The end of the heavy segment. A failure above releases the lock through the helper's EXIT trap.
bench_gate_release

echo "--- Sites this run touched ---"
python3 "$REPO_DIR/scripts/check_site_set.py" compare "$BENCH_DIR" "$SITES_SNAPSHOT"
# SOS-SETUP-18: since the task started (the loop sets SELLOS_TASK_STARTED), or since this run started.
# The bench CLI writes every command line it runs to logs/bench.log, so a password given to
# "bench new-site" ends up there. The tenant site folders are searched whatever their age.
echo "--- No secret (provisioner password, Telegram, BuildOS) is in a log ---"
python3 "$REPO_DIR/scripts/check_no_secret_leak.py" --since "${SELLOS_TASK_STARTED:-$GATE_START}" \
  "$LOG_DIR" "$BENCH_DIR/logs" "$BENCH_DIR/sites/common_site_config.json" "$BENCH_DIR/sites/archived_sites" \
  "$REPO_DIR" "$CLAUDE_TRANSCRIPTS"
python3 "$REPO_DIR/scripts/check_no_secret_leak.py" "$BENCH_DIR"/sites/sellos_tenant_*
echo "--- GATE PASSED ---"
} 2>&1 | sellos_redact | tee "$LOG_FILE"

STATUS="${PIPESTATUS[0]}"
if [[ "$STATUS" -eq 2 || "$STATUS" -eq 3 ]] && [ "$(cat "$SELLOS_ENV_EXIT_FILE" 2>/dev/null)" != "$STATUS" ]; then
  echo "The gate failed with status $STATUS from a command, not from its preflight. Reporting it as a test failure (1)." | tee -a "$LOG_FILE"
  STATUS=1
fi
rm -f "$SELLOS_ENV_EXIT_FILE"
ln -sf "$LOG_FILE" "$LOG_DIR/latest.log"
exit "$STATUS"
