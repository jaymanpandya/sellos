#!/usr/bin/env bash
# flake_check.sh: every new or changed test runs more than once in the gate, and a failure on any run
# is a failure (SOS-SETUP-33). Sourced by scripts/run-tests.sh, never run.
#
# A flaky test is found when it is written, by the agent that can still fix it, not weeks later as a
# rerun that "passed" in someone else's gate. The whole-suite rerun policy (scripts/lib/ui_flaky.sh)
# still applies to specs the task did not change; a changed test gets no rerun and no benefit of the
# doubt. CLAUDE.md "Test rules" says how to write a test that cannot flake.
#
# SOS-SETUP-34: the runs shrink as a test gets slower, measured by its first run: under 60 seconds
# 5 runs, under 3 minutes 3, otherwise 2. The repeats (every run after the first) of one gate get at
# most 10 minutes together (SELLOS_FLAKE_CAP_SECONDS, 600); scripts/lib/flake_plan.py shares them out.
# Every changed test runs once first, then the plan is printed, then the repeats run. A repeat that
# would take the repeats past the cap, judged by the slowest run of that test so far, is not
# started. SELLOS_FLAKE_RUNS lowers every tier to at most that many runs.
#
# It needs from the caller: run_backend (scripts/lib/db_conflict.sh) for a backend module, and
# _sellos_ui_run (scripts/lib/ui_flaky.sh) for a Cypress spec.
#
#   sellos_flake_gate <targets file>     one line per test: "backend|spec<TAB>target<TAB>log prefix"
#   sellos_flake_check <kind> <target> <log prefix>      the same for one test
# Each returns 0 when every run passed, and 1 at the first run that fails (the later runs are not
# needed), after printing "CHANGED TEST FAILED: <module>" or "CHANGED SPEC FAILED: <spec>".

_sellos_flake_now() { date +%s; }

_sellos_flake_run() {
  local kind="$1" target="$2" prefix="$3" run="$4"
  case "$kind" in
    backend) run_backend "$prefix-run$run.log" --module "$target" ;;
    spec) _sellos_ui_run "$prefix-run$run.log" "$target" ;;
  esac
}

_sellos_flake_failed() { # kind target
  if [ "$1" = "spec" ]; then echo "CHANGED SPEC FAILED: $2"; else echo "CHANGED TEST FAILED: $2"; fi
}

sellos_flake_gate() {
  local targets="$1"
  local runs="${SELLOS_FLAKE_RUNS:-5}" cap="${SELLOS_FLAKE_CAP_SECONDS:-600}"
  local plan_py
  plan_py="$(dirname "${BASH_SOURCE[0]}")/flake_plan.py"
  if ! [[ "$runs" =~ ^[1-9][0-9]*$ ]]; then
    echo "SELLOS_FLAKE_RUNS must be a whole number of runs, not '$runs'." >&2
    return 1
  fi
  if ! [[ "$cap" =~ ^[0-9]+$ ]]; then
    echo "SELLOS_FLAKE_CAP_SECONDS must be a whole number of seconds, not '$cap'." >&2
    return 1
  fi
  local kinds=() names=() prefixes=() seconds=() kind target prefix seen
  while IFS=$'\t' read -r kind target prefix; do
    [ -n "$target" ] || continue
    case "$kind" in
      backend | spec) ;;
      *)
        echo "sellos_flake_check: unknown kind '$kind' (backend or spec)" >&2
        return 1
        ;;
    esac
    for seen in ${names[@]+"${names[@]}"}; do [ "$seen" = "$target" ] && continue 2; done
    kinds+=("$kind")
    names+=("$target")
    prefixes+=("$prefix")
  done <"$targets"
  local count="${#names[@]}"
  if [ "$count" -eq 0 ]; then
    echo "=== Repeat plan: no changed test. ==="
    return 0
  fi
  echo "=== Repeat plan: $count changed test(s): ${names[*]}"
  echo "    Each runs once first. Then a test whose first run took under 60s runs 5 times in all,"
  echo "    under 3 minutes 3 times, otherwise 2 times, and the repeats get at most ${cap}s together. ==="

  # Run 1 of every test, timed. A failure here is a plain failure, not a flaky one.
  local i start status work
  work="$(mktemp -d "${TMPDIR:-/tmp}/sellos-flake.XXXXXX")"
  : >"$work/durations"
  for ((i = 0; i < count; i++)); do
    echo "--- Flake check: ${names[i]}, run 1 ---"
    start="$(_sellos_flake_now)"
    status=0
    _sellos_flake_run "${kinds[i]}" "${names[i]}" "${prefixes[i]}" 1 || status=$?
    seconds[i]=$(($(_sellos_flake_now) - start))
    if [ "$status" -ne 0 ]; then
      rm -rf "$work"
      _sellos_flake_failed "${kinds[i]}" "${names[i]}"
      return 1
    fi
    printf '%s\t%s\t%s\n' "${kinds[i]}" "${names[i]}" "${seconds[i]}" >>"$work/durations"
  done

  # The plan, from the first runs.
  if ! SELLOS_FLAKE_RUNS="$runs" SELLOS_FLAKE_CAP_SECONDS="$cap" \
    python3 "$plan_py" plan "$work/durations" "$work/plan"; then
    rm -rf "$work"
    echo "The repeat plan could not be made (scripts/lib/flake_plan.py)." >&2
    return 1
  fi
  local planned=() line
  while IFS= read -r line; do planned+=("$line"); done <"$work/plan"
  rm -rf "$work"

  # The repeats, never past the cap.
  # A repeat is expected to take as long as the slowest run of that test so far.
  local used=0 run passed total took slowest
  for ((i = 0; i < count; i++)); do
    total="${planned[i]:-1}"
    passed=" 1"
    slowest="${seconds[i]}"
    for ((run = 2; run <= total; run++)); do
      if [ $((used + slowest)) -gt "$cap" ]; then
        echo "Repeat cap: ${names[i]} stops after run $((run - 1)) of $total: run $run would take the repeats past ${cap}s (${used}s used)."
        total=$((run - 1))
        break
      fi
      echo "--- Flake check: ${names[i]}, run $run of $total ---"
      start="$(_sellos_flake_now)"
      status=0
      _sellos_flake_run "${kinds[i]}" "${names[i]}" "${prefixes[i]}" "$run" || status=$?
      took=$(($(_sellos_flake_now) - start))
      used=$((used + took))
      [ "$took" -gt "$slowest" ] && slowest="$took"
      if [ "$status" -ne 0 ]; then
        echo "GUARD FAILED: flake-check"
        echo "Fix: ${names[i]} passed on run(s)${passed} and failed on run $run of $total, so it is flaky, and a flaky test is a failure. Find the race and remove it, never retry or lengthen a wait: no real background jobs in tests (run the job's function directly), wait on a condition never on time (no sleep, no cy.wait(<ms>)), and no shared mutable state (make your own uniquely named records, restore what you change). CLAUDE.md, Test rules."
        echo "The failing run's log: ${prefixes[i]}-run$run.log"
        echo "END GUARD"
        _sellos_flake_failed "${kinds[i]}" "${names[i]}"
        return 1
      fi
      passed="$passed $run"
    done
    echo "Flake check: ${names[i]} passed $total of $total runs."
  done
  echo "Flake check: the repeats took ${used}s of ${cap}s."
  return 0
}

sellos_flake_check() {
  local file status=0
  file="$(mktemp "${TMPDIR:-/tmp}/sellos-flake-one.XXXXXX")"
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >"$file"
  sellos_flake_gate "$file" || status=$?
  rm -f "$file"
  return "$status"
}
