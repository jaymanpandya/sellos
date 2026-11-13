#!/usr/bin/env bash
# flake_check.sh: every new or changed test runs SELLOS_FLAKE_RUNS (5) times in the gate, and a failure
# on any run is a failure (SOS-SETUP-33). Sourced by scripts/run-tests.sh, never run.
#
# A flaky test is found when it is written, by the agent that can still fix it, not weeks later as a
# rerun that "passed" in someone else's gate. The whole-suite rerun policy (scripts/lib/ui_flaky.sh)
# still applies to specs the task did not change; a changed test gets no rerun and no benefit of the
# doubt. CLAUDE.md "Test rules" says how to write a test that cannot flake.
#
# It needs from the caller: run_backend (scripts/lib/db_conflict.sh) for a backend module, and
# _sellos_ui_run (scripts/lib/ui_flaky.sh) for a Cypress spec.
#
#   sellos_flake_check backend <dotted.module> <log prefix>
#   sellos_flake_check spec <path under cypress/integration> <log prefix>
# Returns 0 when every run passed, 1 at the first run that fails (the later runs are not needed).

sellos_flake_check() {
  local kind="$1" target="$2" prefix="$3"
  local runs="${SELLOS_FLAKE_RUNS:-5}" run status passed=""
  if ! [[ "$runs" =~ ^[1-9][0-9]*$ ]]; then
    echo "SELLOS_FLAKE_RUNS must be a whole number of runs, not '$runs'." >&2
    return 1
  fi
  for ((run = 1; run <= runs; run++)); do
    echo "--- Flake check: $target, run $run of $runs ---"
    status=0
    case "$kind" in
      backend) run_backend "$prefix-run$run.log" --module "$target" || status=$? ;;
      spec) _sellos_ui_run "$prefix-run$run.log" "$target" || status=$? ;;
      *)
        echo "sellos_flake_check: unknown kind '$kind' (backend or spec)" >&2
        return 1
        ;;
    esac
    if [ "$status" -ne 0 ]; then
      if [ "$run" -gt 1 ]; then
        echo "GUARD FAILED: flake-check"
        echo "Fix: $target passed on run(s)${passed} and failed on run $run of $runs, so it is flaky, and a flaky test is a failure. Find the race and remove it, never retry or lengthen a wait: no real background jobs in tests (run the job's function directly), wait on a condition never on time (no sleep, no cy.wait(<ms>)), and no shared mutable state (make your own uniquely named records, restore what you change). CLAUDE.md, Test rules."
        echo "The failing run's log: $prefix-run$run.log"
        echo "END GUARD"
      fi
      return 1
    fi
    passed="$passed $run"
  done
  echo "Flake check: $target passed $runs of $runs runs."
  return 0
}
