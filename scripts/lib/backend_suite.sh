#!/usr/bin/env bash
# backend_suite.sh: run the backend tests the way the gate does, from CI too (SOS-SETUP-33).
#
#   SITE=<site> APP=sellos scripts/lib/backend_suite.sh <log file> [run-tests options...]
#
# Run from the bench folder. It is run_backend (scripts/lib/db_conflict.sh): the command goes through
# report_test_exit.sh, which prints every batch and the exit code, and a module that failed on a
# MariaDB 1020 or deadlock is rerun once, alone; a second conflict exits 3. The gate sources
# db_conflict.sh itself; CI's Server job runs this file, so both apply the same policy.
set -uo pipefail
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${SITE:?SITE must be set}" "${APP:?APP must be set}"
LOG="${1:?usage: backend_suite.sh <log file> [run-tests options...]}"
shift
export REPORT_TEST_EXIT="$LIB/report_test_exit.sh"
export DB_CONFLICT="$LIB/db_conflict.py"
export DB_CONFLICT_LOG="${DB_CONFLICT_LOG:-$(dirname "$LOG")/sellos-db-conflict.log}"
if ! declare -F sellos_env_exit >/dev/null; then
  sellos_env_exit() { exit "$1"; }
fi
# shellcheck source=db_conflict.sh
source "$LIB/db_conflict.sh"
mkdir -p "$(dirname "$LOG")"
run_backend "$LOG" "$@"
exit $?
