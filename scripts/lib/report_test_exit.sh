#!/usr/bin/env bash
# report_test_exit.sh: run a test command, then say plainly what it returned (SOS-SETUP-24).
#
#   scripts/lib/report_test_exit.sh bench --site <site> run-tests --app sellos
#
# The command's output passes through unchanged. Afterwards this prints the summary of every batch
# the runner ran and the command's exit code, and exits with that code.
#
# Why: Frappe's run-tests runs the integration tests and the other tests as two batches, each with
# its own "Ran N tests" and "OK" or "FAILED". On 10 November 2026 (CI run 42830839891) the first
# batch said FAILED (errors=3) and the second, printed last, said "Ran 238 tests ... OK", so the
# step looked as if the tests had passed and the runner had failed for no reason. The exit code
# was right. A summary line proves nothing; the exit code does.
set -uo pipefail

if [ "$#" -eq 0 ]; then
  echo "usage: report_test_exit.sh <test command> [args...]" >&2
  exit 2
fi

log="$(mktemp "${TMPDIR:-/tmp}/sellos-test-exit.XXXXXX")"
trap 'rm -f "$log"' EXIT

"$@" 2>&1 | tee "$log"
status="${PIPESTATUS[0]}"

# The runner's own lines, with any colour codes taken off.
plain() { sed -E $'s/\x1b\\[[0-9;]*m//g' "$log"; }
summary="$(plain | grep -E '^(Running [0-9]+ .*tests? for |Ran [0-9]+ tests? in |OK( \(.*\))?$|FAILED( \(.*\))?$)' || true)"
# Each FAILED line, with the batch it ended ("Running 43 integration tests for sellos").
failed="$(printf '%s\n' "$summary" | awk '/^Running /{batch=$0} /^FAILED/{print "    " $0 "  <- " (batch ? batch : "batch not named")}')"
ran="$(printf '%s\n' "$summary" | awk '/^Ran [0-9]+ test/{n+=$2} END{print n+0}')"

echo
echo "=== Test command: $*"
if [ -n "$summary" ]; then
  echo "=== Every batch the runner ran:"
  printf '%s\n' "$summary" | sed 's/^/    /'
fi
echo "=== Exit code of the test command: $status"

if [ "$status" -ne 0 ]; then
  if [ -n "$failed" ]; then
    echo "A test batch failed, and the runner returned $status. The last summary is not the whole result:"
    printf '%s\n' "$failed"
  elif [ -n "$summary" ]; then
    echo "tests passed but the runner returned $status"
  else
    echo "The runner returned $status and printed no test summary."
  fi
elif [ "$ran" -eq 0 ]; then
  # A filter that matches nothing runs no test and still exits 0.
  echo "The runner returned 0 but ran no tests."
  exit 1
fi
exit "$status"
