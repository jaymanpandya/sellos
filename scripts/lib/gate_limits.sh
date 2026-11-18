#!/usr/bin/env bash
# gate_limits.sh: hard time limits for the commands inside the gate (SOS-SETUP-39). Sourced, never run.
#
# scripts/run-tests.sh sets SELLOS_GATE_LIMITS=1 and sources this; then sellos_limited runs a command
# under scripts/lib/gate_watch.py, which kills SellOS's own process tree when the limit is passed.
# CI sources ui_flaky.sh and db_conflict.sh without it, so there sellos_limited just runs the command.
#
#   sellos_limited <label> <seconds> <command...>   the command's own status, or 124 on a timeout
#   sellos_limit_check <status> <label>             after a limited command: 124 or 125 ends the gate
#                                                   with status 4 (a gate timeout, an environment fault)
SELLOS_GATE_WATCH_PY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/gate_watch.py"

sellos_limited() {
  local label="$1" seconds="$2"
  shift 2
  if [ -z "${SELLOS_GATE_LIMITS:-}" ]; then
    "$@"
    return $?
  fi
  python3 "$SELLOS_GATE_WATCH_PY" run --label "$label" --timeout "$seconds" \
    --fault-file "${SELLOS_GATE_FAULT_FILE:-}" -- "$@"
}

sellos_limit_check() {
  case "$1" in
    124 | 125)
      echo "GATE TIMEOUT: $2 did not finish in time (status $1). The gate stops with status 4; the loop treats it as an environment fault, not the task's."
      exit 4
      ;;
  esac
  return 0
}
