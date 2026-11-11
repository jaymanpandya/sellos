#!/usr/bin/env bash
# ui_flaky.sh: the one rerun policy for Cypress, used by scripts/run-tests.sh (the local gate) and by
# the UI job in .github/workflows/ci.yml (SOS-SETUP-27). Neither runs the Cypress suite any other way,
# so the two cannot drift. sellos/tests/test_ui_flaky_policy.py tests the policy and the wiring.
#
# CI run 42925739766 failed on one spec that the local gate had passed. The gate reruns a failed
# spec once and CI did not, so one flake stopped the loop (DEV_STRATEGY.md section 4, row 31).
#
# The policy:
# * Run the suite, or one spec. A spec that fails is rerun once, alone, after a clear-cache.
# * A rerun that passes is logged "FLAKY (passed on rerun): <spec>", added to the flaky log, and the
#   run passes. A rerun that fails is "FAILED AGAIN: <spec>" and the run fails.
# * More than SELLOS_MAX_RERUN (5) failed specs, or a failure no spec can be named for, fails at once.
# * A spec in the flaky log SELLOS_FLAKY_LIMIT (3) times or more fails the run until it is fixed.
#   To clear it after the fix: the local gate's log is $HOME/iespl-baseline/sellos-flaky.log; CI's is
#   the Actions cache with the key prefix sellos-flaky- (gh cache delete).
# * When GITHUB_STEP_SUMMARY is set, the flaky specs of this run go in the job summary.
#
# Run it (CI):     SITE=test_site APP=sellos SELLOS_FLAKY_LOG=... scripts/lib/ui_flaky.sh <log> [spec]
# Or source it and call sellos_ui_suite <log> [spec] (the gate, which has sellos_redact defined: the
# Cypress output then goes through it before it reaches the log file).
# <spec> is a path under cypress/integration, such as crm/consent_warning.cy.js.
# Returns 0 when the run passes and 1 when it fails.

SELLOS_UI_FLAKY_PY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ui_flaky.py"

_sellos_ui_filter() {
  if declare -F sellos_redact >/dev/null; then sellos_redact; else cat; fi
}

_sellos_ui_summary() {
  [ -n "${GITHUB_STEP_SUMMARY:-}" ] || return 0
  printf '%s\n' "$@" >>"$GITHUB_STEP_SUMMARY"
}

# _sellos_ui_run <log> [spec]: one Cypress run, its output through the filter into <log> and stdout.
# Prints nothing of its own. Returns Cypress's exit status, not the filter's.
_sellos_ui_run() {
  local log="$1" spec="${2:-}" status
  if [ -n "$spec" ]; then
    bench --site "$SITE" run-ui-tests "$APP" --headless --spec "cypress/integration/$spec" 2>&1 \
      | _sellos_ui_filter | tee "$log"
  else
    bench --site "$SITE" run-ui-tests "$APP" --headless 2>&1 | _sellos_ui_filter | tee "$log"
  fi
  status="${PIPESTATUS[0]}"
  return "$status"
}

sellos_ui_suite() {
  local log="$1" spec="${2:-}"
  local flaky_log="${SELLOS_FLAKY_LOG:?SELLOS_FLAKY_LOG must name the flaky log}"
  local max="${SELLOS_MAX_RERUN:-5}" limit="${SELLOS_FLAKY_LIMIT:-3}"
  local status=0 failed count s n still=0 flaky_now="" repeat
  : "${SITE:?SITE must be set}" "${APP:?APP must be set}"
  mkdir -p "$(dirname "$flaky_log")"
  touch "$flaky_log"

  _sellos_ui_run "$log" "$spec" || status=$?
  if [ "$status" -ne 0 ]; then
    if [ -n "$spec" ]; then
      failed="$spec"
    else
      failed="$(python3 "$SELLOS_UI_FLAKY_PY" failed-specs "$log")"
    fi
    count="$(printf '%s\n' "$failed" | grep -c . || true)"
    if [ -z "$failed" ] || [ "$count" -gt "$max" ]; then
      echo "--- UI tests failed ($count specs identified), not rerunning ---"
      _sellos_ui_summary "### Cypress" "" "UI tests failed ($count specs identified), not rerun."
      return 1
    fi
    for s in $failed; do
      echo "--- RERUN once, alone: $s ---"
      bench --site "$SITE" clear-cache || true
      if _sellos_ui_run "${log%.log}-rerun-$(printf '%s' "$s" | tr '/' '_').log" "$s"; then
        echo "FLAKY (passed on rerun): $s"
        echo "$(date +%F) $s" >>"$flaky_log"
        flaky_now="$flaky_now $s"
      else
        echo "FAILED AGAIN: $s"
        still=1
      fi
    done
  fi

  if [ -n "$flaky_now" ]; then
    _sellos_ui_summary "### Flaky Cypress specs" "" \
      "Each failed, then passed when rerun once, alone. $limit times in the flaky log fails the run." "" \
      "| Spec | Times in the flaky log |" "| --- | --- |"
    for s in $flaky_now; do
      n="$(python3 "$SELLOS_UI_FLAKY_PY" count "$flaky_log" "$s")"
      _sellos_ui_summary "| \`$s\` | $n |"
    done
  elif [ "$status" -eq 0 ]; then
    _sellos_ui_summary "### Flaky Cypress specs" "" "None: every spec passed on its first run."
  fi
  if [ "$still" -ne 0 ]; then
    _sellos_ui_summary "" "A spec failed again on its rerun, so the run failed."
    return 1
  fi

  # A spec that keeps needing a rerun is hiding a real fault. Three strikes and the run stops.
  repeat="$(python3 "$SELLOS_UI_FLAKY_PY" too-flaky "$flaky_log" "$limit")"
  if [ -n "$repeat" ]; then
    echo "--- FLAKY too often, fix these specs: $(printf '%s' "$repeat" | tr '\n' ' ')---"
    _sellos_ui_summary "" "**FLAKY too often, fix these specs:** $(printf '%s' "$repeat" | tr '\n' ' ')"
    return 1
  fi
  return 0
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  set -uo pipefail
  if [ "$#" -lt 1 ]; then
    echo "Usage: SITE=... APP=... SELLOS_FLAKY_LOG=... $0 <cypress log> [spec]" >&2
    exit 2
  fi
  sellos_ui_suite "$@"
  exit $?
fi
