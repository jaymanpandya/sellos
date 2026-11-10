#!/usr/bin/env bash
# db_conflict.sh: run_backend for scripts/run-tests.sh (SOS-SETUP-25). Sourced, never run.
#
# It needs these set by the caller: REPORT_TEST_EXIT (scripts/lib/report_test_exit.sh), SITE, APP,
# DB_CONFLICT (scripts/lib/db_conflict.py) and DB_CONFLICT_LOG, and the function sellos_env_exit
# (scripts/lib/sellos_server.sh).
#
# SOS-SETUP-25: run backend tests, and treat a MariaDB 1020 ("Record has changed since last read")
# or a deadlock as a retryable infrastructure error. It is a timing race with another connection,
# usually the shared bench worker, and on 10 November 2026 one Blocked SOS-P1-06A after using up
# its repair runs. When the failure log holds one, only the failing modules are rerun, once each,
# alone. A rerun that hits one again exits 3, an environment problem the loop never repairs. A
# rerun that fails any other way is a test failure. Returns the test command's status.
#
#   run_backend <log file> [run-tests options...]
run_backend() {
  local log="$1" status mod failed rerun_log
  shift
  "$REPORT_TEST_EXIT" bench --site "$SITE" run-tests --app "$APP" "$@" 2>&1 | tee "$log"
  status="${PIPESTATUS[0]}"
  [ "$status" -eq 0 ] && return 0
  python3 "$DB_CONFLICT" is-conflict "$log" || return "$status"
  failed="$(python3 "$DB_CONFLICT" failing-modules "$log")"
  if [ -z "$failed" ]; then
    echo "A database conflict (1020 or deadlock) is in the log, but no failing module could be named. Not rerunning."
    return "$status"
  fi
  for mod in $failed; do
    echo "--- DATABASE CONFLICT (1020 or deadlock): RERUN once, alone: $mod ---"
    rerun_log="${log%.log}-rerun-$mod.log"
    "$REPORT_TEST_EXIT" bench --site "$SITE" run-tests --app "$APP" --module "$mod" 2>&1 | tee "$rerun_log"
    status="${PIPESTATUS[0]}"
    if [ "$status" -eq 0 ]; then
      echo "DATABASE CONFLICT (passed on rerun): $mod"
      echo "$(date +%F) $mod" >>"$DB_CONFLICT_LOG"
      continue
    fi
    if python3 "$DB_CONFLICT" is-conflict "$rerun_log"; then
      echo "database conflict (1020), not a code failure"
      sellos_env_exit 3
    fi
    return "$status"
  done
  return 0
}
