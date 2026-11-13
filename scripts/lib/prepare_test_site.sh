#!/usr/bin/env bash
# prepare_test_site.sh: migrate a test site and make it a clean company site by code (SOS-SETUP-33).
#
#   scripts/lib/prepare_test_site.sh <site> [app]      run from the bench folder
#
# The one way the gate (after it restores the baseline), CI's Server job and CI's UI job prepare
# their site, so the three start from the same state: migrate, clear the cache, run
# sellos.tests.ui_fixtures.prepare_clean_site (the state a provisioned company site is in, and the
# role users, made by code on every run, DEV_STRATEGY.md row 11), and clear the cache again.
set -euo pipefail
SITE="${1:?usage: prepare_test_site.sh <site> [app]}"
APP="${2:-sellos}"
echo "--- Migrating $SITE ---"
bench --site "$SITE" migrate
bench --site "$SITE" clear-cache
echo "--- Preparing the clean site (code, every run) ---"
bench --site "$SITE" execute "$APP.tests.ui_fixtures.prepare_clean_site"
bench --site "$SITE" clear-cache
