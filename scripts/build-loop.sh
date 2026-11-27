#!/usr/bin/env bash
# build-loop.sh — the SellOS autonomous build loop.
#
# Run this from the sellos app repo (or anywhere — it locates
# itself relative to this script's own path). Each cycle:
#   1. Pick the next task (select-next-task.sh).
#   2. Mark it In Progress and commit that immediately.
#   3. Call `claude -p` once with the task embedded in the prompt.
#   4. On IMPLEMENTATION_READY: run the real test gate (run-tests.sh).
#      Pass -> mark Complete, commit, push. Fail -> mark Blocked, notify, go on (SOS-SETUP-37).
#   5. On NEEDS_INPUT: notify and stop — a human needs to answer.
#   6. On a crashed Claude process: mark Blocked, notify, go on (SOS-SETUP-37).
#   7. On an environment problem (SOS-SETUP-14): the gate exits 2 or 3, or the server preflight
#      fails after a failed gate run. Notify and stop, leaving the task In Progress and the
#      working tree untouched: no repair run, no reset, no salvage, not Blocked. Restarting the
#      loop resumes the task.
#   8. SOS-SETUP-18: the agent runs with every credential variable removed from its environment
#      except SELLOS_DB_PROVISIONER_USER (scripts/lib/db_secrets.sh). The provisioner password is
#      removed too (SOS-SETUP-22), and so is every BUILDOS_ variable (SOS-SETUP-29).
#      Everything this script prints, every reply it saves and every notification is redacted, so
#      their values never reach the loop log, NOTIFY, Telegram or a gate log.
#
# The loop stops itself on needs-input, no-work and two Blocked tasks in a row.
#
# SOS-SETUP-37: a Blocked task does not idle the loop. On 14 November 2026 SOS-P1-20 was Blocked at
# 12:55 IST and the loop stood idle for two days with eligible work left. Now the loop sends the
# notice, records the stop in docs/STOPS.md (idle 0.0, committed with the Blocked status), and picks
# the next Not Started task whose dependencies are all Complete. tasks.py never picks a Blocked task,
# and a Blocked dependency is unmet, so nothing that depends on one, directly or through other
# tasks, is picked either. Two tasks Blocked in a row stop the loop: that is more likely the loop's
# own fault than two bad tasks. A Blocked task is never auto-resumed. Root-cause the failure,
# verify it by hand (including actually browsing the result, not just re-reading logs), then run
# `scripts/set-task-status.sh <TASK_ID> "Not Started"` yourself.
#
# NO BROKEN CODE EVER LANDS ON MAIN: this script records the commit
# HEAD was at before each task starts. On any non-clean outcome for
# that task (Claude crashes, gives an unrecognized response, needs
# input, or fails its tests) the repo is hard-reset back to that exact
# commit before marking the task Blocked. Only a task whose tests
# actually pass gets its changes committed and pushed. This means a
# Blocked task's own commit message describes the failure, but none of
# the code that caused it is still sitting on main to be picked up
# accidentally by a later task.
#
# NOT YET WIRED, NEEDS YOUR INPUT: there is no "deploy" step. The OTT
# loop finishes a passing task with `docker compose up -d --build`;
# SellOS has no equivalent yet since bench runs locally, not in
# containers. SellOS's server is `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`.
# If you want the loop to also restart/reload that server
# (or `bench build` for JS assets) after every Complete so dev_site
# reflects the change live, tell me how bench is currently being run
# (foreground terminal, tmux/screen, or something else) and I'll add
# that step — restarting it wrong could kill your working dev session,
# so it's deliberately left out rather than guessed at.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TASKS_FILE="$PROJECT_DIR/TASKS.md"
LOCK_FILE="${SELLOS_LOOP_LOCK:-/tmp/sellos-build-loop.lock}"
# The gate writes its logs here too (scripts/run-tests.sh reads the same variable).
LOG_DIR="${SELLOS_LOG_DIR:-/tmp/sellos-test-logs}"
TASK_BLOCK_PATH="${SELLOS_TASK_BLOCK_PATH:-/tmp/sellos-task-block.md}"
BRANCH="${SELLOS_BRANCH:-1.0}"

# SOS-SETUP-34: every commit the loop makes goes through loop_commit, which takes every CI skip marker
# ([skip ci], [ci skip], [no ci], [skip actions], skip-checks: true and the like) out of its message
# (scripts/lib/commit_message.py), so no loop commit ever skips CI. Use it as git commit, with -m or -F.
loop_commit() {
  local args=() msg
  while (($#)); do
    case "$1" in
      -m)
        msg="$(printf '%s\n' "$2" | python3 "$SCRIPT_DIR/lib/commit_message.py" clean)" || return 1
        args+=(-m "$msg")
        shift 2
        ;;
      -F)
        python3 "$SCRIPT_DIR/lib/commit_message.py" clean-file "$2" || return 1
        args+=(-F "$2")
        shift 2
        ;;
      *)
        args+=("$1")
        shift
        ;;
    esac
  done
  git commit "${args[@]}"
}

# SOS-SETUP-33: the stop ledger. Every way this script ends, except "another loop is running", appends
# one row to docs/STOPS.md (time, task, category, cause, minutes the attempt took) through the EXIT
# trap, and prints the hours since the last stop. The next start commits the row with the idle time. Each stop site sets its category and
# cause with stop_note first; anything that ends the loop without one (set -e, a signal) is still
# recorded, as "unexpected" or "stopped". The next start fills in how long the loop stood idle.
STOPS_FILE="$PROJECT_DIR/docs/STOPS.md"
STOPS_PY="$SCRIPT_DIR/lib/stops.py"
# SOS-SETUP-39: a hung or frozen gate must be impossible to miss and impossible to leave stuck.
# The loop and everything it starts carry SELLOS_GATE_TAG, so the leftover Cypress and headless Chrome
# processes of SellOS, and only those, are found by lib/gate_watch.py (never BuildOS's or Pamaa's).
# Before each gate and after any stop they are killed. Limits are in seconds, chosen from the gate's
# measured times (docs/STOPS.md): the whole gate 150 min (a normal run is 31 to 51 min, plus up to 90
# min waiting for the bench lock), and 15 min without a new line in the loop log.
GATE_WATCH="$SCRIPT_DIR/lib/gate_watch.py"
export SELLOS_GATE_TAG="sellos-loop-$(printf '%s' "$PROJECT_DIR" | cksum | cut -d' ' -f1)"
SELLOS_GATE_TIMEOUT="${SELLOS_GATE_TIMEOUT:-9000}"
SELLOS_STALL_TIMEOUT="${SELLOS_STALL_TIMEOUT:-900}"
export SELLOS_GATE_FAULT_FILE="${SELLOS_GATE_FAULT_FILE:-$LOG_DIR/gate-fault.txt}"
cleanup_leftovers() {
  echo "Looking for SellOS's own leftover Cypress and Chrome processes ($1)."
  python3 "$GATE_WATCH" cleanup --tag "$SELLOS_GATE_TAG" || true
}
STOP_CATEGORY="unexpected"
STOP_CAUSE="the loop ended without saying why (a failed command under set -e)"
STOP_TASK="-"
stop_note() { STOP_CATEGORY="$1"; STOP_CAUSE="$2"; }
on_exit() {
  local status=$? minutes=0
  if [[ "$(cat "$LOCK_FILE" 2>/dev/null)" == "$$" ]]; then rm -f "$LOCK_FILE"; fi
  [[ "$STOP_CATEGORY" == "none" ]] && return
  cleanup_leftovers "after the stop"
  if [[ "$STOP_TASK" != "-" && -n "${SELLOS_TASK_STARTED:-}" ]]; then
    minutes=$((($(date +%s) - SELLOS_TASK_STARTED) / 60))
  fi
  [[ "$STOP_CATEGORY" == "unexpected" ]] && STOP_CAUSE="$STOP_CAUSE, exit $status"
  # Not committed here: an environment stop leaves the tree exactly as it was. The next start commits it.
  python3 "$STOPS_PY" record "$STOPS_FILE" "$STOP_TASK" "$STOP_CATEGORY" "$STOP_CAUSE" "$minutes" || true
  echo "Stop recorded in docs/STOPS.md: $STOP_CATEGORY, $STOP_TASK. $(python3 "$STOPS_PY" summary "$STOPS_FILE" "$PROJECT_DIR" 2>/dev/null)"
}
trap on_exit EXIT
trap 'stop_note stopped "stopped by a signal (sellos stop --now, Ctrl-C or a shutdown)"; exit 143' TERM INT HUP

# SOS-SETUP-18: the provisioner account's values never reach the loop's log. Everything this script
# and its children print goes through the redaction filter from here on.
# shellcheck source=lib/db_secrets.sh
source "$SCRIPT_DIR/lib/db_secrets.sh"
# SOS-SETUP-22: the provisioner password is in the variable or in the macOS Keychain item
# sellos_provisioner. The check below never reads the value (no -w). It is then loaded into the
# loop's own environment, before the output filter starts, so the filter and the gate's leak check
# know it. The agent never gets it: its code reads the Keychain through get_provisioner_password().
if ! sellos_provisioner_available; then
  echo "The MariaDB provisioner password is not in SELLOS_DB_PROVISIONER_PASSWORD and the Keychain item sellos_provisioner is missing. Store it once with: $SELLOS_STORE_COMMAND"
  stop_note start "the provisioner password is missing"
  "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: the provisioner password is missing. Store it once with: $SELLOS_STORE_COMMAND" >/dev/null 2>&1 || true
  exit 3
fi
sellos_load_provisioner_password || true
exec > >(sellos_redact) 2>&1
echo "The provisioner password is available (variable or Keychain). The agent gets only SELLOS_DB_PROVISIONER_USER."

# SOS-SETUP-20: the BuildOS loop runs at the same time. The two gates share only the heavy segment,
# through the bench gate lock in scripts/run-tests.sh. Nothing else is serialised.

if [[ -f "$LOCK_FILE" ]]; then
  OLD_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Another build-loop.sh is already running (pid $OLD_PID) against this repo. Exiting."
    stop_note none "another loop is running"
    exit 1
  fi
  echo "Stale lock file found (pid ${OLD_PID:-unknown}, not running). Removing."
  rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
# The loop starts: fill in how long it stood idle since the last stop, commit that, and say how long
# it has run without a stop (SOS-SETUP-33).
# Only docs/STOPS.md is committed, whatever else the tree holds (an In Progress task's work stays as it is).
if [[ -f "$STOPS_FILE" ]]; then
  python3 "$STOPS_PY" restarted "$STOPS_FILE" || true
  git -C "$PROJECT_DIR" add -- docs/STOPS.md >/dev/null 2>&1 || true
  if ! git -C "$PROJECT_DIR" diff --cached --quiet -- docs/STOPS.md 2>/dev/null; then
    (cd "$PROJECT_DIR" && loop_commit -q -m "SOS-LOOP: the last stop and the restart, in docs/STOPS.md" -- docs/STOPS.md) || true
  fi
fi
echo "$(python3 "$STOPS_PY" summary "$STOPS_FILE" "$PROJECT_DIR" 2>/dev/null)"

cd "$PROJECT_DIR"

# SOS-SETUP-21, once per loop start, not per task. The bench gate lock helper every gate sources must
# be the copy this repository keeps (scripts/shared). A missing or different copy is reinstalled.
INSTALLED_HELPER="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}/bench-gate-lock.sh"
if ! cmp -s "$SCRIPT_DIR/shared/bench-gate-lock.sh" "$INSTALLED_HELPER"; then
  echo "WARNING: $INSTALLED_HELPER is missing or differs from scripts/shared/bench-gate-lock.sh. Reinstalling it."
  if ! "$SCRIPT_DIR/install-shared-helpers.sh"; then
    stop_note start "the bench gate lock helper could not be installed"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: could not install the bench gate lock helper at $INSTALLED_HELPER. Stopping before any task starts." || true
    exit 3
  fi
fi
# The agent reads BuildOS only in this read only copy, never under apps/buildos.
if ! REFERENCE_OUT="$("$SCRIPT_DIR/refresh-buildos-reference.sh" 2>&1)"; then
  echo "$REFERENCE_OUT"
  stop_note environment "the BuildOS reference copy could not be refreshed"
  "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: Environment problem, not the task. The BuildOS reference copy could not be refreshed. Stopping before any task starts:
$REFERENCE_OUT" || true
  exit 3
fi
echo "$REFERENCE_OUT"

# Nobody is at the keyboard: git must fail at once instead of waiting for a password or a host key.
export GIT_TERMINAL_PROMPT=0
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
if [[ "$ORIGIN_URL" == ssh://* || "$ORIGIN_URL" =~ ^[^/:]+@[^/:]+: ]]; then
  export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=15"
fi

# What went wrong in the last gate run: the unit test failures, the browser test failures, and the end of the log.
# SOS-SETUP-32: both prompts carry this. On 13 November 2026 the SOS-N21A agent wrote a phone number
# as map(str, range(...)) so test_no_raw_phone_numbers would not match it, Semgrep flagged that, the
# first repair turned it back into a literal, and the task was Blocked. The guard's message named the
# fix (sellos.tests.phones) the whole time.
GUARD_RULES="Guards. Some tests check the code itself rather than a feature: sellos/tests/test_no_raw_phone_numbers.py, the no-commands check in sellos/provisioning/test_p1_02_worker.py, the permission matrix, the secret leak checks, Semgrep and the lint rules. When one fails, read its whole message before anything else: it says what is wrong and names the fix (for a phone number, generate it with sellos.tests.phones, for example in_mobile(seed), and derive every other form from it, such as its ten national digits or its spoken words). Apply that fix in your own code. Never work around a guard: never disguise what it looks for (no concatenation, joins, ranges, escapes, encodings, comments or computed strings), never move code to a folder the guard skips just to escape it (code goes where the guard says it belongs: commands only in sellos/provisioning, through its existing helpers), never add to an allowed list, and never edit the guard. Read every failing test in the failure output, in every batch, not only the first, and fix all of them in this pass."

# SOS-SETUP-33: every guard runs in scripts/check-guards.sh in under 30 seconds with no database. The
# agent runs it before it replies, and docs/GUARDS.md (each guard, why, how to comply, an example)
# goes into both prompts, so a guard is met while the agent still has the context, not after a
# twenty minute gate run.
GUARDS_DOC="$(cat "$PROJECT_DIR/docs/GUARDS.md" 2>/dev/null || echo "docs/GUARDS.md is missing.")"
GUARDS_CHECK="Before you reply, run scripts/check-guards.sh from the app folder (it takes under 30 seconds and needs no database) and fix every GUARD FAILED block it prints, the way its Fix line says, then run it again until it prints GUARDS PASSED. The gate runs the same guards first and a task that fails one goes back to repair. This is docs/GUARDS.md:
$GUARDS_DOC"

# SOS-SETUP-32: what the repair agent sees of a failed gate run. On 13 November 2026 SOS-N21A was
# Blocked after its repair runs never saw the failing guard: this kept only the last failed batch,
# cut it at 150 lines, which one traceback's local variables filled, and the 25 line tail began one
# line after the guard's message. Now every failing test in every batch comes first, each with its
# assertion message (which for a guard names the fix), then each failed batch with its locals left
# out, then the last lines of the run.
failure_context() {
  local log="$LOG_DIR/latest.log"
  if [[ ! -f "$log" ]]; then log="$(ls -t "$LOG_DIR"/run-*.log 2>/dev/null | head -1)"; fi
  if [[ -z "$log" || ! -f "$log" ]]; then echo "no log available"; return; fi
  local eq; eq="$(printf '=%.0s' $(seq 1 70))"
  {
    echo "--- every failing test, in every batch, with its message (read each one; a guard's message names its fix):"
    # From a FAIL or ERROR header, skip the traceback and print the exception line and the message
    # under it, up to the next separator, at most 25 lines each.
    awk -v eq="$eq" '
      /^ ?(FAIL|ERROR):? / {print; inblk=1; msg=0; n=0; next}
      inblk && ($0==eq || /^-{70}$/ && msg) {inblk=0; msg=0; next}
      inblk && !msg && /^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception|Failure|Exit)(:|$)/ {msg=1}
      inblk && msg && n<25 {print "    " $0; n++}
    ' "$log" | head -200
    echo "--- each failed backend batch (local variables left out):"
    awk -v eq="$eq" '
      {L[NR]=$0}
      $0==eq {if (bs==0 || bs<prevran) bs=NR}
      /^Ran [0-9]+ tests/ {prevran=NR}
      /^FAILED \(/ {print "[batch]"; for (i=bs;i<=NR;i++) print L[i]; bs=0}
    ' "$log" | grep -v -E '^    [A-Za-z_][A-Za-z0-9_]* = ' | head -200
    echo "--- browser test failures:"
    awk '/^  [0-9]+\) /{c=14} c>0{print; c--}' "$log" | head -150
    echo "--- last lines of the run:"
    tail -n 40 "$log"
  } | cut -c1-300
}

# SOS-SETUP-33: the GUARD FAILED blocks of the last gate run (scripts/check-guards.sh), each with its
# Fix line, exactly as the guard printed them. Empty when no guard failed.
guard_failures() {
  local log="$LOG_DIR/latest.log"
  if [[ ! -f "$log" ]]; then log="$(ls -t "$LOG_DIR"/run-*.log 2>/dev/null | head -1)"; fi
  if [[ -z "$log" || ! -f "$log" ]]; then return 0; fi
  awk '/^GUARD FAILED: /{inblk=1} inblk{print} /^END GUARD$/{inblk=0}' "$log" | head -300 | cut -c1-400
}

# SOS-SETUP-33: a repair after a failed guard starts with the guard's own message and this rule, before
# anything else, so the agent applies the fix the guard names instead of hiding what it looks for.
# On 13 November 2026 the SOS-N21A repairs fixed one guard by breaking another (docs/DEV_STRATEGY.md row 38).
GUARD_RULE="Do not work around a guard; apply the fix it names."
repair_head() {
  local fails
  fails="$(guard_failures)"
  [[ -z "$fails" ]] && return 0
  printf '%s\n%s\n%s\n\n' "A guard failed. $GUARD_RULE" "$fails" "Apply each Fix above in your own code, then run scripts/check-guards.sh and repeat until it prints GUARDS PASSED. $GUARD_RULE"
}

# SOS-SETUP-37: the specs the task did not change but uses (a test id in a changed screen, or a changed
# API method), as the gate's last run left them in $LOG_DIR/affected-specs.txt, each with why and
# whether it passed. A repair after one failed starts with them. Empty when the gate found none.
affected_context() {
  local file="$LOG_DIR/affected-specs.txt" failed
  [[ -s "$file" ]] || return 0
  failed="$(awk -F '\t' '$1 == "FAILED" {print "  " $2 " (" $3 ")"}' "$file")"
  printf '%s\n' "Specs this task did not change but that use what it changed (a test id in a changed screen, or a changed API method). The gate ran each once, before anything else:"
  awk -F '\t' '{print "  " $1 ": " $2 " (" $3 ")"}' "$file"
  if [[ -n "$failed" ]]; then
    printf '%s\n%s\n' "These failed, so this task broke them:" "$failed"
    printf '%s\n' "Read each failure in the output below. Update every spec that uses the control or test id you changed (grep cypress/ for it), through one shared helper in cypress/support/commands.js where several specs do the same thing. Never weaken or delete an assertion."
  fi
  printf '\n'
}

is_limit() { printf '%s\n' "$1" | grep -q -i -E "hit your .*limit|usage limit|limit reached"; }
wait_for_limit() {
  local secs
  secs="$(python3 "$SCRIPT_DIR/limit_wait.py" "$1")"
  echo "Claude's usage limit was reached. Waiting $((secs / 60)) minutes for it to reset, then carrying on."
  "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: usage limit reached. Waiting $((secs / 60)) minutes, then continuing." >/dev/null 2>&1 || true
  sleep "$secs"
}

# After a push, wait for every CI run on that commit. Red, or no run found, means stop.
# SOS-SETUP-28: a red run whose jobs failed before any step ran is what a spent Actions budget (or a
# billing problem) looks like. CI_RED_REASON then says so, and the stop notice carries it: the fix
# is minutes, not code (DEV_STRATEGY.md section 4, row 32).
CI_RED_REASON=""
# SOS-SETUP-38: CI_FAILED_IDS holds the runs that failed, and CI_ENV_REASON says why a red run is the
# environment's (jobs that never started, or no run at all), for ci_until_green below.
CI_FAILED_IDS=""
CI_ENV_REASON=""
CI_FIRST_WAIT="${SELLOS_CI_FIRST_WAIT:-20}"
ci_green() {
  local sha="$1" ids="" i=0 id rc=0 unstarted
  CI_RED_REASON=""
  CI_FAILED_IDS=""
  CI_ENV_REASON=""
  while [[ $i -lt 12 && -z "$ids" ]]; do
    ids="$(gh run list --branch "$BRANCH" --commit "$sha" --json databaseId --jq '.[].databaseId' 2>/dev/null || true)"
    [[ -z "$ids" ]] && sleep 10
    i=$((i + 1))
  done
  if [[ -z "$ids" ]]; then
    echo "No CI run found for $sha."
    CI_ENV_REASON="no CI run was found for $sha (GitHub Actions did not start one)"
    return 1
  fi
  sleep "$CI_FIRST_WAIT"
  ids="$(gh run list --branch "$BRANCH" --commit "$sha" --json databaseId --jq '.[].databaseId' 2>/dev/null || echo "$ids")"
  for id in $ids; do
    if ! gh run watch "$id" --exit-status >/dev/null 2>&1; then
      echo "CI run $id failed."
      rc=1
      CI_FAILED_IDS="${CI_FAILED_IDS:+$CI_FAILED_IDS }$id"
      unstarted="$(python3 "$SCRIPT_DIR/lib/ci_minutes.py" never-started "$id" 2>/dev/null || true)"
      if [[ -n "$unstarted" ]]; then
        CI_RED_REASON="CI run $id: these jobs never started ($unstarted). The Actions minutes budget may be spent, or billing needs attention. This is not a code failure."
        CI_ENV_REASON="$CI_RED_REASON"
        echo "$CI_RED_REASON"
      fi
    fi
  done
  return $rc
}

# SOS-SETUP-38: a red CI on a head the loop pushed does not stop the loop when the loop can repair it.
# On 16 November 2026 CI run 43954312044 went red on 757df9c (a test pinned a real task's status, and
# a spec left a request running) and the loop stood stopped until a person fixed two test files.
# ci_until_green reads the failed jobs' logs (scripts/lib/ci_failures.py) and:
#   * a fault outside the code (a runner lost, jobs GitHub would not start, quota, network, no run at
#     all): rerun the failed jobs once; green goes on, red stops (category environment);
#   * a failing test: up to SELLOS_MAX_CI_REPAIRS (2) repair attempts, each one an agent given the
#     failing tests and their messages, the gate, a commit, a push and a wait for CI. Green goes on;
#     both attempts failing stops (category ci-red). A repair never starts on a tree that already has
#     uncommitted work, and a failed attempt's changes stay in the tree for the next attempt.
# Every step sends a Telegram message. On a stop it returns 1 with CI_STOP_CATEGORY, CI_STOP_CAUSE and
# CI_STOP_NOTICE set; the caller records the stop and ends the loop.
MAX_CI_REPAIRS="${SELLOS_MAX_CI_REPAIRS:-2}"
CI_STOP_CATEGORY=""
CI_STOP_CAUSE=""
CI_STOP_NOTICE=""
CI_FAILURES=""
CI_KIND=""

# SOS-SETUP-43: GitHub gives no log for a run, or a job, that has not completed ("run N is still in
# progress; logs will be available when it is complete"). On 18 November 2026 the loop read run
# 44391986098 in that state, saw no failing test, and spent both repair attempts on nothing. So wait
# for the run to complete, then read the failed jobs' log (gh run view --log-failed, the same text as
# gh api repos/<repo>/actions/jobs/<id>/logs), and treat the "not available yet" text as a reason to
# wait again, never as a log. 1 when no log could be read within SELLOS_CI_LOG_WAIT seconds.
CI_LOG_WAIT="${SELLOS_CI_LOG_WAIT:-1800}"
CI_LOG_POLL="${SELLOS_CI_LOG_POLL:-20}"
ci_log_pending() { grep -qiE 'still in progress|logs will be available|log not found|logs? (is|are) not available' "$1"; }
ci_read_run_log() {
  local id="$1" log="$2" status out started=$SECONDS
  out="$(mktemp)"
  while true; do
    status="$(gh run view "$id" --json status --jq .status 2>/dev/null || true)"
    if [[ "$status" == completed ]]; then
      gh run view "$id" --log-failed >"$out" 2>&1 || true
      if [[ -s "$out" ]] && ! ci_log_pending "$out"; then
        cat "$out" >>"$log"
        rm -f "$out"
        return 0
      fi
    fi
    if [[ $((SECONDS - started)) -ge "$CI_LOG_WAIT" ]]; then
      rm -f "$out"
      return 1
    fi
    sleep "$CI_LOG_POLL"
  done
}

# The failed jobs' logs of CI_FAILED_IDS, then CI_FAILURES (the failing tests and their messages) and
# CI_KIND ("code", or "environment <why>").
ci_read_failures() {
  local id log="$LOG_DIR/ci-failed.log" unread=""
  mkdir -p "$LOG_DIR"
  : >"$log"
  for id in $CI_FAILED_IDS; do
    ci_read_run_log "$id" "$log" || unread="${unread:+$unread, }$id"
  done
  CI_FAILURES="$(sellos_redact_text "$(python3 "$SCRIPT_DIR/lib/ci_failures.py" extract "$log" 2>/dev/null || true)")"
  if [[ -n "$CI_ENV_REASON" ]]; then
    CI_KIND="environment $CI_ENV_REASON"
  elif [[ -n "$unread" ]]; then
    # SOS-SETUP-43: no log is no evidence. It is never a failure to repair, so it never costs a repair attempt.
    CI_KIND="environment the log of CI run $unread was still not readable after ${CI_LOG_WAIT}s"
  else
    CI_KIND="$(python3 "$SCRIPT_DIR/lib/ci_failures.py" kind "$log" 2>/dev/null || echo code)"
  fi
  if [[ -z "$CI_FAILURES" ]]; then
    CI_FAILURES="(no failing test could be read from the log; its last lines:)
$(sellos_redact_text "$(tail -n 30 "$log" | cut -c1-300)")"
  fi
}

# Rerun the failed jobs of CI_FAILED_IDS once and wait for them. 0 when every one is then green.
ci_rerun_failed() {
  local id rc=0
  [[ -n "$CI_FAILED_IDS" ]] || return 1
  for id in $CI_FAILED_IDS; do
    gh run rerun "$id" --failed >/dev/null 2>&1 || { echo "gh could not rerun CI run $id."; rc=1; continue; }
  done
  [[ "$rc" -eq 0 ]] || return 1
  sleep "$CI_FIRST_WAIT"
  for id in $CI_FAILED_IDS; do
    gh run watch "$id" --exit-status >/dev/null 2>&1 || { echo "CI run $id is still red after its rerun."; rc=1; }
  done
  return $rc
}

ci_notify() { "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $1" || true; }

# The flake counter alone is red (CI runs 44557395802, 44561474025, 44566130220 on SOS-P2-05: no test
# failed on its own, the counter said "FLAKY too often"). Editing the specs by guesswork twice fixed
# nothing, so this never costs a repair attempt: rerun the failed jobs once; if the counter is still
# the only red, write the specs to docs/FLAKY.md (only that file is committed) and go on.
ci_record_flaky() {
  local log="$LOG_DIR/ci-failed.log" specs
  specs="$(python3 "$SCRIPT_DIR/lib/ci_failures.py" flaky "$log" 2>/dev/null || true)"
  [[ -n "$specs" ]] || specs="(the specs could not be read from the log)"
  mkdir -p docs
  if [[ ! -f docs/FLAKY.md ]]; then
    printf '%s\n' "# Flaky specs" "" \
      "Written by the loop (scripts/build-loop.sh, ci_until_green) when CI was red only because of the flake" \
      "counter and still was after one rerun of the failed jobs. The loop went on. Fix a spec from its real" \
      "failure message, never by guesswork, then clear the counter (docs/CI.md)." "" \
      "| Date | Commit | Task | Specs |" "| --- | --- | --- | --- |" >docs/FLAKY.md
  fi
  printf '| %s | %s | %s | %s |\n' "$(date '+%F %H:%M')" "$1" "$2" "$(printf '%s' "$specs" | tr '\n' ' ')" >>docs/FLAKY.md
  git add docs/FLAKY.md
  loop_commit -q -m "SOS-LOOP: flaky specs recorded in docs/FLAKY.md after CI went red on the flake counter alone ($1)" -- docs/FLAKY.md || true
}

# ci_until_green <what was pushed, for the messages> <task id or ->
ci_until_green() {
  local label="$1" task="$2" sha attempt=0 started=0 gate_exit response summary repair_log
  CI_STOP_CATEGORY=""
  CI_STOP_CAUSE=""
  CI_STOP_NOTICE=""
  sha="$(git rev-parse --short HEAD)"
  ci_green "$(git rev-parse HEAD)" && return 0
  while true; do
    ci_read_failures
    if [[ "$CI_KIND" == flake-counter ]]; then
      ci_notify "CI is red on $label ($sha) only because of the flake counter (no test failed on its own). No repair attempt is spent. Rerunning the failed jobs once."
      if ci_rerun_failed; then
        ci_notify "CI is green on $label ($sha) after one rerun of the failed jobs. Going on."
        return 0
      fi
      ci_read_failures
      if [[ "$CI_KIND" == flake-counter ]]; then
        ci_record_flaky "$sha" "$task"
        ci_notify "CI is still red on $label ($sha) with only the flake counter after the rerun. The specs are in docs/FLAKY.md. Going on without a repair."
        return 0
      fi
    fi
    if [[ "$CI_KIND" == environment* ]]; then
      local why="${CI_KIND#environment }"
      ci_notify "CI is red on $label ($sha), and the cause is outside the code: $why. Rerunning the failed jobs once."
      if ci_rerun_failed; then
        ci_notify "CI is green on $label ($sha) after one rerun of the failed jobs. Going on."
        return 0
      fi
      CI_STOP_CATEGORY=environment
      CI_STOP_CAUSE="CI red on $sha ($label) for a reason outside the code, still red after one rerun: $why"
      CI_STOP_NOTICE="CI is still red on $label ($sha) after one rerun, and the cause is outside the code: $why. Stopping, nothing new started. Fix the runner, quota or network, then restart the loop."
      return 1
    fi
    if [[ "$attempt" -ge "$MAX_CI_REPAIRS" ]]; then
      CI_STOP_CATEGORY=ci-red
      CI_STOP_CAUSE="CI still red on $sha ($label) after $attempt repair attempt(s): $(printf '%s\n' "$CI_FAILURES" | head -n 2 | tr '\n' ' ' | cut -c1-200)"
      CI_STOP_NOTICE="CI is still red on $label ($sha) after $attempt repair attempt(s). Stopping, nothing new started. Still failing:
$CI_FAILURES"
      return 1
    fi
    if [[ "$started" -eq 0 && -n "$(git status --porcelain)" ]]; then
      CI_STOP_CATEGORY=ci-red
      CI_STOP_CAUSE="CI red on $sha ($label), and the working tree holds uncommitted work, so a repair would mix it in"
      CI_STOP_NOTICE="CI is red on $label ($sha). The working tree holds uncommitted work (an In Progress task's), so the loop did not repair it: the repair would be committed with that work. Stopping. Failing:
$CI_FAILURES"
      return 1
    fi
    started=1
    attempt=$((attempt + 1))
    ci_notify "CI is red on $label ($sha). Repair attempt $attempt of $MAX_CI_REPAIRS. Failing:
$CI_FAILURES"
    set +e
    response="$(sellos_agent_env claude -p "The CI run on the pushed commit $sha ($label) is red. The working tree is the pushed code$([[ -n "$(git status --porcelain)" ]] && echo ", plus the changes of the last repair attempt, whose gate run failed (its failures are after the CI ones)"). Find the cause of every failure below in the code and fix it. This is CI repair attempt $attempt of $MAX_CI_REPAIRS.
$GUARD_RULES
$GUARDS_CHECK
Rules. Fix the cause, in the product code or in the test. Never delete or weaken an assertion, never add a retry, never raise a limit (the flaky limit included), and never skip a test. A test that asserts a value the loop changes (a real task's status in TASKS.md, a row of docs/STOPS.md) is fixed by asserting only what stays true, or by a fixture the test writes itself. A spec that ends with a request still running is fixed by stubbing or waiting for that request. Never edit a gate file: scripts/run-tests.sh, scripts/build-loop.sh, anything under scripts/lib or scripts/shared, scripts/check_*.py, cypress.config.js, cypress/support/e2e.js, .github/workflows, docs/DEV_STRATEGY.md, docs/TESTING.md, docs/STOPS.md, docs/GUARDS.md, sellos/testing/guards.py or scripts/check-guards.sh. You may run the single backend test module or the single browser spec you changed, one at a time and in the foreground, from ~/iespl-bench: bench --site sellos_test.localhost run-tests --app sellos --module <dotted.module.path>, or bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/<path>. Never run the full suite, and never run anything in the background. Never run git commit, git push, git reset, git stash, git rebase, git merge, git checkout of another branch or set-task-status.sh: the loop commits and pushes after the gate passes. Never run seed_regression_data, any ui_fixtures.seed_* function or scripts/prepare-regression.sh. The word Frappe must never appear in any user facing label, screen, or error message.
Respond with this as the literal first characters of your response, nothing before it:
IMPLEMENTATION_READY: <plain English summary of what you fixed>

Failing in CI (test, then its message):
$CI_FAILURES$([[ -n "$(git status --porcelain)" ]] && printf '\n\nThe last repair attempt'"'"'s gate run failed:\n%s' "$(failure_context)")" --dangerously-skip-permissions)"
    set -e
    response="$(sellos_redact_text "$response")"
    mkdir -p "$LOG_DIR"
    repair_log="$LOG_DIR/claude-ci-repair-${task}-$(date +%Y%m%d-%H%M%S).txt"
    printf '%s\n' "$response" >"$repair_log"
    summary="$(printf '%s\n' "$response" | grep -m1 -E '^IMPLEMENTATION_READY:' || true)"
    summary="${summary#IMPLEMENTATION_READY: }"
    if [[ -z "$(git status --porcelain)" ]]; then
      ci_notify "CI repair attempt $attempt of $MAX_CI_REPAIRS on $label changed nothing, so nothing was pushed."
      continue
    fi
    set +e
    run_gate_guarded
    gate_exit=$?
    set -e
    if [[ "$gate_exit" -eq 2 || "$gate_exit" -eq 3 ]]; then
      CI_STOP_CATEGORY=environment
      CI_STOP_CAUSE="the gate stopped in its preflight (exit $gate_exit) during CI repair attempt $attempt on $sha ($label)"
      CI_STOP_NOTICE="CI repair attempt $attempt on $label: the gate stopped before testing anything (exit $gate_exit), an environment problem. The repair's changes are left uncommitted in the working tree. Stopping.
$(tail -n 15 "$GATE_OUT")"
      return 1
    fi
    if [[ "$gate_exit" -ne 0 ]]; then
      ci_notify "CI repair attempt $attempt of $MAX_CI_REPAIRS on $label failed the gate, so nothing was pushed. Its changes stay in the working tree for the next attempt.
$(grep -m3 -E 'GUARDS FAILED|AFFECTED SPECS FAILED|CHANGED TEST FAILED|CHANGED SPEC FAILED|BACKEND TESTS FAILED|UI TESTS FAILED|SMOKE TESTS FAILED' "$GATE_OUT" 2>/dev/null || tail -n 5 "$GATE_OUT")"
      continue
    fi
    git add -A
    loop_commit -q -m "SOS-LOOP: repair of the red CI on $sha ($label), attempt $attempt

${summary:-the repair passed the gate}"
    if ! push_with_retry; then
      CI_STOP_CATEGORY=push-failed
      CI_STOP_CAUSE="the push of CI repair attempt $attempt failed after every retry"
      CI_STOP_NOTICE="CI repair attempt $attempt on $label passed the gate and is committed, but the push failed after every retry. The commit is kept; the next start pushes it first. Stopping. git said:
$(printf '%s' "$PUSH_ERROR" | head -c 3000)"
      return 1
    fi
    sha="$(git rev-parse --short HEAD)"
    ci_notify "CI repair attempt $attempt of $MAX_CI_REPAIRS on $label passed the gate and is pushed as $sha. Waiting for CI."
    if ci_green "$(git rev-parse HEAD)"; then
      ci_notify "CI is green on $sha after repair attempt $attempt. Going on."
      return 0
    fi
  done
}

# SOS-LOOP (27 November 2026): push_with_retry lives in scripts/lib/push_retry.sh. A rejected push
# is fixed by git pull --rebase --autostash origin 1.0 and pushed again (three attempts); only a real
# rebase conflict stops, after git rebase --abort, with the conflicted files named in PUSH_ERROR.
source "$SCRIPT_DIR/lib/push_retry.sh"

# SOS-SETUP-14: an environment problem is not a task failure. The gate exits 2 or 3 only from its
# preflight (wrong site or port, a server that is down or is not SellOS, no baseline, no Semgrep,
# another gate running), never because of the task's code: run-tests.sh maps every other failure to
# 1. A server that dies in the middle of a Cypress run makes the gate exit 1, so after every failed
# gate run the loop runs the gate's own server preflight again (scripts/lib/sellos_server.sh: the
# port, ping, and the guest /sellos redirect). If it fails, the failure is the environment's.
BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
TEST_SITE="${SELLOS_TEST_SITE:-sellos_test.localhost}"
GATE_OUT="$LOG_DIR/loop-gate-output.txt"

# SOS-SETUP-39: run the gate under a hard timeout and a stall watchdog (lib/gate_watch.py). Past the
# whole-gate limit, or with no new line in the loop log for the stall limit, SellOS's own process tree
# is killed, the bench lock is released, the reason goes to Telegram, and the gate is run once more.
# A gate timeout (status 4 from a limit inside the gate, 124 or 125 from here) is an environment
# fault: never repaired as code. A second one stops the loop with the stop reason "gate timeout".
# The caller has set +e. Returns the gate's status; a timeout that survives the rerun ends the loop.
gate_timeout_status() { [[ "$1" -eq 4 || "$1" -eq 124 || "$1" -eq 125 ]]; }
release_dead_gate_lock() {
  local dir="${BENCH_GATE_LOCK_DIR:-/tmp/iespl-bench-heavy.lock.d}" holder
  holder="$(cat "$dir/pid" 2>/dev/null || true)"
  if [[ -d "$dir" && -n "$holder" ]] && ! kill -0 "$holder" 2>/dev/null; then
    rm -rf "$dir"
    echo "Released the bench gate lock held by pid $holder, which is gone."
  fi
}
run_gate_guarded() {
  local attempt=1 code reason
  while true; do
    cleanup_leftovers "before the gate"
    rm -f "$SELLOS_GATE_FAULT_FILE"
    python3 "$GATE_WATCH" run --label "the gate" --timeout "$SELLOS_GATE_TIMEOUT" \
      --stall "$SELLOS_STALL_TIMEOUT" --stall-file "${SELLOS_LOOP_LOG:-$GATE_OUT}" \
      --fault-file "$SELLOS_GATE_FAULT_FILE" -- "$SCRIPT_DIR/run-tests.sh" 2>&1 | sellos_redact | tee "$GATE_OUT"
    code="${PIPESTATUS[0]}"
    gate_timeout_status "$code" || return "$code"
    reason="$(cat "$SELLOS_GATE_FAULT_FILE" 2>/dev/null || true)"
    [[ -n "$reason" ]] || reason="gate timeout: the gate ended with status $code"
    cleanup_leftovers "after the gate timeout"
    release_dead_gate_lock
    if [[ "$attempt" -ge 2 ]]; then
      echo "Gate timeout again: $reason. Stopping."
      stop_note "gate timeout" "$reason, on two gate runs in a row"
      "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: GATE TIMEOUT again, so the loop is stopping. $reason.
${TASK_ID:-The task} stays In Progress and its work is left in the working tree as it is: no repair run, no reset, not Blocked. This is an environment fault (a hung gate, or the Mac slept), not the code's.
Check the Mac (power, sleep), then restart the loop with: scripts/sellos up" || true
      exit 3
    fi
    echo "Gate timeout: $reason. An environment fault, not the code's: running the gate once more."
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: GATE TIMEOUT. $reason. Its process tree is killed and the bench lock is released. Not handed to the repair agent; the gate runs once more, and a second timeout stops the loop." || true
    attempt=$((attempt + 1))
  done
}
# shellcheck source=lib/sellos_server.sh
source "$SCRIPT_DIR/lib/sellos_server.sh"

# The gate's server preflight. Prints its message, and returns 0, 2 (port) or 3 (server).
server_preflight() {
  (
    sellos_require_port "$BENCH_DIR" "$TEST_SITE"
    sellos_preflight "$TEST_SITE" "$PORT"
  ) 2>&1
}

# Connection errors to a server: Cypress (cy.visit / cy.request "failed trying to load", with the
# network error under it), Node, curl and Python requests.
CONNECTION_ERROR_RE='ECONNREFUSED|ECONNRESET|ESOCKETTIMEDOUT|socket hang up|failed trying to load|request failed without a response|We received this error at the network level|Connection refused|Failed to connect|Max retries exceeded|NewConnectionError|RemoteDisconnected'
# Lines that report a failure. Summary lines (counts, "failed again", the run table) only repeat
# the failures above them, so they are not causes.
FAILURE_LINE_RE='Error|Exception|Traceback|AssertionError|expected .* to |FAIL:|ERROR:'
SUMMARY_LINE_RE='FAILED \(|FAILED AGAIN|SPEC FAILED|SMOKE TEST|UI tests failed|Failing:|[0-9]+ of [0-9]+ failed|│|GATE PASSED'

# True when the gate's output has a connection error to the SellOS server and every failure line
# in it is a connection error, as when the server dies in the middle of a Cypress run.
only_connection_errors() {
  local out="$1" other
  [[ -f "$out" ]] || return 1
  grep -E "$CONNECTION_ERROR_RE" "$out" | grep -q -E "(${TEST_SITE//./\\.}|127\.0\.0\.1|localhost|\[::1\]):$SELLOS_PORT" ||
    grep -A3 -E 'failed trying to load' "$out" | grep -q -E "(${TEST_SITE//./\\.}|127\.0\.0\.1|localhost):$SELLOS_PORT" ||
    return 1
  other="$(grep -E "$FAILURE_LINE_RE" "$out" | grep -v -E "$CONNECTION_ERROR_RE" | grep -v -E "$SUMMARY_LINE_RE" || true)"
  [[ -z "$other" ]]
}

# Stop the loop for an environment problem. The task stays In Progress, and its work stays in the
# working tree exactly as it is: no repair run, no reset, no salvage, not Blocked. The next start
# of the loop resumes the In Progress task.
stop_for_environment() {
  local why="$1" detail="$2"
  echo "Environment problem, not the task: $why"
  printf '%s\n' "$detail"
  stop_note environment "$why"
  "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: Environment problem, not the task. $why
$TASK_ID stays In Progress and its work is left in the working tree as it is: no repair run, no reset, no salvage, not Blocked.
The gate said:
$(printf '%s' "$detail" | tail -c 3000)
Fix it, then restart the loop. It resumes $TASK_ID." || true
  exit 3
}

# Before any task starts: the remote must answer, and anything committed but not pushed goes up first.
if ! LS_REMOTE_OUT="$(git ls-remote --exit-code origin HEAD 2>&1)"; then
  echo "git cannot reach the remote (origin). Stopping before any task starts."
  printf '%s\n' "$LS_REMOTE_OUT"
  stop_note start "git cannot reach origin"
  "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: git cannot reach the remote (origin). Stopping before any task starts. git said:
$(printf '%s' "$LS_REMOTE_OUT" | head -c 3000)" || true
  exit 1
fi
if ! FETCH_OUT="$(git fetch origin "$BRANCH" 2>&1)"; then
  printf '%s\n' "$FETCH_OUT"
  stop_note start "could not fetch $BRANCH"
  "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: could not fetch $BRANCH from origin. Stopping before any task starts. git said:
$(printf '%s' "$FETCH_OUT" | head -c 3000)" || true
  exit 1
fi
# The loop waits for CI after every push, so gh must be signed in before anything starts.
if ! GH_AUTH_OUT="$(gh auth status 2>&1)"; then
  echo "gh is not signed in, so the loop cannot watch CI. Stopping before any task starts."
  printf '%s\n' "$GH_AUTH_OUT"
  stop_note start "gh is not signed in"
  "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: gh auth status failed, so CI cannot be watched. Stopping before any task starts. gh said:
$(printf '%s' "$GH_AUTH_OUT" | head -c 3000)" || true
  exit 1
fi
# SOS-SETUP-38: status commits are not pushed alone. A commit that changes nothing but TASKS.md and
# docs/STOPS.md ("mark In Progress", a Blocked status, a stop ledger row) goes to origin only with the
# next push that carries code (a task's completion), so CI never runs on a status commit. On 16 November
# 2026 the loop pushed "SOS-P1-07: mark In Progress" alone at its start, CI ran on it, went red on a
# test that pinned P1-07's status, and the loop stopped (CI run 43954312044).
is_status_commit() {
  local f
  while IFS= read -r f; do
    [[ -z "$f" || "$f" == "TASKS.md" || "$f" == "docs/STOPS.md" ]] || return 1
  done < <(git diff-tree --no-commit-id --name-only -r "$1")
  return 0
}
AHEAD="$(git rev-list --count "origin/$BRANCH..$BRANCH" 2>/dev/null || echo 0)"
CODE_AHEAD=0
for c in $(git rev-list "origin/$BRANCH..$BRANCH" 2>/dev/null); do
  is_status_commit "$c" || CODE_AHEAD=$((CODE_AHEAD + 1))
done
if [[ "$AHEAD" -gt 0 && "$CODE_AHEAD" -eq 0 ]]; then
  echo "$BRANCH is $AHEAD status commit(s) ahead of origin (TASKS.md and docs/STOPS.md only). Not pushing them alone: they go up with the next task's completion push, so CI never runs on a status commit."
elif [[ "$AHEAD" -gt 0 ]]; then
  AHEAD_LIST="$(git log --reverse --format='%h %s' "origin/$BRANCH..$BRANCH" | cut -c1-160)"
  BAD_LIST="$(git log --format='%h %s' "origin/$BRANCH..$BRANCH" | awk '$2 !~ /^SOS-/' | cut -c1-160)"
  if [[ -n "$BAD_LIST" ]]; then
    echo "$BRANCH has unpushed commits whose message does not start with SOS-. Not pushing them."
    printf '%s\n' "$BAD_LIST"
    stop_note push-failed "unpushed commits that do not start with SOS-"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $BRANCH is $AHEAD commit(s) ahead of origin, and these do not start with SOS-, so nothing was pushed. Stopping before any task starts:
$BAD_LIST" || true
    exit 1
  fi
  echo "$BRANCH is $AHEAD commit(s) ahead of origin, $CODE_AHEAD of them with code. Pushing them before any task starts:"
  printf '%s\n' "$AHEAD_LIST"
  if ! push_with_retry; then
    stop_note push-failed "pushing the commits that were ahead failed"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $BRANCH is $AHEAD commit(s) ahead of origin and the push failed. Stopping before any task starts. The commits are kept:
$AHEAD_LIST
git said:
$(printf '%s' "$PUSH_ERROR" | head -c 3000)" || true
    exit 1
  fi
  "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: pushed $AHEAD commit(s) that were ahead of origin. Waiting for CI before picking a task:
$AHEAD_LIST" || true
  if ! ci_until_green "the commits that were ahead" -; then
    stop_note "$CI_STOP_CATEGORY" "$CI_STOP_CAUSE"
    ci_notify "$CI_STOP_NOTICE"
    exit 1
  fi
fi

# SOS-SETUP-37: what happens after a task is marked Blocked. blocked_decide runs after the status is
# set and before the commit: the first Blocked task in a row gets its docs/STOPS.md row now, idle 0.0,
# staged so it goes into the Blocked commit (an uncommitted ledger would fail the next task's
# gate-files guard), and the loop goes on. A second Blocked task in a row is a stop: the EXIT trap
# records it. blocked_notice adds the Blocked list to the notice and says which way the loop went.
BLOCKED_IN_A_ROW=0
LAST_BLOCKED=""
BLOCKED_STOP=0
blocked_decide() {
  local category="$1" cause="$2" minutes=0
  BLOCKED_IN_A_ROW=$((BLOCKED_IN_A_ROW + 1))
  if [[ -n "${SELLOS_TASK_STARTED:-}" ]]; then minutes=$((($(date +%s) - SELLOS_TASK_STARTED) / 60)); fi
  if [[ "$BLOCKED_IN_A_ROW" -ge 2 ]]; then
    BLOCKED_STOP=1
    stop_note "$category" "two tasks Blocked in a row ($LAST_BLOCKED, then $TASK_ID): $cause"
  else
    BLOCKED_STOP=0
    python3 "$STOPS_PY" record "$STOPS_FILE" "$TASK_ID" "$category" "$cause; the loop went on to the next task" "$minutes" 0 || true
    git add -- docs/STOPS.md >/dev/null 2>&1 || true
  fi
  LAST_BLOCKED="$TASK_ID"
}
blocked_notice() {
  local list
  list="$(python3 "$SCRIPT_DIR/lib/tasks.py" blocked "$TASKS_FILE" 2>/dev/null | head -10 || true)"
  if [[ "$BLOCKED_STOP" -eq 1 ]]; then
    printf '%s\n%s\n%s' "$1 Two tasks Blocked in a row, so the loop stops." "Blocked:" "$list"
  else
    printf '%s\n%s\n%s' "$1 Going on with the next eligible task, skipping the Blocked ones and everything that depends on them." "Blocked:" "$list"
  fi
}

# A scheduled regression pause (SOS-SETUP-19): scripts/pause-loop.sh creates this file and
# scripts/resume-loop.sh removes it. It is checked before every pick, so a running task finishes first.
PAUSE_FILE="${SELLOS_PAUSE_FILE:-/tmp/sellos-loop.pause}"

while true; do
  STOP_TASK="-"
  if [[ -e "$PAUSE_FILE" ]]; then
    echo "Paused for regression: $PAUSE_FILE exists. Nothing picked. Run scripts/resume-loop.sh, then start the loop again."
    stop_note paused "the regression pause file exists"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: Paused for regression. Nothing picked. Run scripts/resume-loop.sh after the regression, then start the loop again." || true
    break
  fi

  TASK_ID="$("$SCRIPT_DIR/select-next-task.sh" "$TASKS_FILE")"

  if [[ "$TASK_ID" == "NONE_ELIGIBLE" ]]; then
    stop_note no-work "no eligible task: the Waiting tasks hold up the rest"
    WAITING_LINES="$(python3 "$SCRIPT_DIR/lib/tasks.py" waiting "$TASKS_FILE" | head -12 || true)"
    if [[ -n "$WAITING_LINES" ]]; then
      "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: no eligible tasks left. Stopping. Waiting tasks that hold up Not Started work (finish one by hand with scripts/set-task-status.sh <ID> Complete TASKS.md, then commit and push):
$WAITING_LINES"
    else
      "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: no eligible tasks left. Stopping."
    fi
    break
  fi


  echo "Selected task: $TASK_ID"
  STOP_TASK="$TASK_ID"
  # SOS-SETUP-39: a Mac on battery power, or under 30 percent, can sleep or run out in the middle of a gate.
  if ! POWER_NOW="$(python3 "$GATE_WATCH" power --warn)"; then
    echo "WARNING: the Mac is $POWER_NOW."
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: starting $TASK_ID with the Mac $POWER_NOW. A gate can hang if it sleeps, or stop when the battery runs out. Plug it in." || true
  fi

  # Known-good point to fall back to if this task doesn't end cleanly.
  PRE_TASK_SHA="$(git rev-parse HEAD)"

  TASK_BLOCK="$(awk -v id="$TASK_ID" '
    $0 ~ "^### " id ":" { printing = 1; print; next }
    printing && /^### / { exit }
    printing { print }
  ' "$TASKS_FILE")"

  TASK_TITLE="$(printf '%s\n' "$TASK_BLOCK" | head -n 1 | sed -E 's/^### [^:]+: *//')"
  CURRENT_STATUS="$(printf '%s\n' "$TASK_BLOCK" | grep -m1 '\*\*Status:\*\*' | sed -E 's/.*\*\*Status:\*\* *//')"

  if [[ "$CURRENT_STATUS" == "Not Started" ]]; then
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "In Progress" "$TASKS_FILE"
    git add "$TASKS_FILE"
    loop_commit -m "$TASK_ID: mark In Progress"
  fi

  IP_SHA="$(git rev-parse HEAD)"
  # The gate and scripts/check-guards.sh run the task guards from these. SOS-SETUP-33: they are set
  # before the agent starts, so the agent's own run of scripts/check-guards.sh checks the task too.
  printf '%s\n' "$TASK_BLOCK" > "$TASK_BLOCK_PATH"
  export SELLOS_TASK_ID="$TASK_ID"
  export SELLOS_BASE_SHA="$IP_SHA"
  export SELLOS_TASK_BLOCK_FILE="$TASK_BLOCK_PATH"
  # The gate's secret leak check searches every file changed since this moment.
  export SELLOS_TASK_STARTED="$(date +%s)"

  PROMPT="You are implementing one task from SellOS's TASKS.md inside the
sellos Frappe v16 app. Never run the full test suite or the whole browser suite, and never run anything in the background. Never start, stop or touch the servers on port 8000 (BuildOS) or 8002 (Pamaa); SellOS runs only on port 8004, on the server Jayman starts with cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004. You may, and should, run the single backend test module and the single browser spec that you add or change, one at a time and in the foreground: for a module, from ~/iespl-bench, bench --site sellos_test.localhost run-tests --app sellos --module <dotted.module.path>; for a spec, from ~/iespl-bench, bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/<path>. Fix whatever fails before you reply. When you change a control or a test id (data-testid), or what a form needs before it saves, grep cypress/ for it and update every spec that uses it, not only your own; where several specs do the same thing, change them through one shared helper in cypress/support/commands.js. The gate runs every spec that uses a test id in a screen you changed, or an API method you changed, before anything else (SOS-SETUP-37). The loop then runs scripts/run-tests.sh separately and blocks on its real result. Never run git commit, git push, git reset, git stash, git rebase, git merge, git checkout of another branch or set-task-status.sh, and never change a task's status: the loop does all of that after the gate passes. Leave your work uncommitted in the working tree. Never run seed_regression_data, any ui_fixtures.seed_* function or scripts/prepare-regression.sh, with bench execute or any other way: only prepare-regression.sh, run by a person, seeds the regression data. Check a seed change with a backend test that calls it and reads it back. A task whose block says Browser spec: required also adds its flows to docs/regression/flows.md, one line each in the form FLOW <task id>-<n> | role | start path | steps | expected result (see that file). Add flows, never remove or change one, and if the task adds data a person sees, add it to seed_regression_data in sellos/tests/ui_fixtures.py through the production API and update its docstring.
Follow SellOS's locked architecture: no ERPNext. The web app never uses
the Frappe desk, and every customer feature is built in the SellOS web
app. There are five roles: Platform Admin, Company Admin, Agent, Client
and Channel Partner. Every company is its own site and database, so
isolation is by site. Consent never blocks: a lead's consent status
(Consented, Unknown, Opted out, Registered DND when known) is recorded and
shown as a warning on the lead, the caller queue and the call log, and never
prevents a call, an SMS or a WhatsApp message, in code or in the screens.
Enforcement lives in one function behind the company setting Consent
enforcement, which is Off by default. The 022 number is for service and
transactional calls. The product is called SellOS everywhere, with no
company or suite brand. The word 'Frappe' must never appear in any user
facing label, screen, or error message.

Shared bench (SOS-SETUP-20): the BuildOS loop runs on this bench at the
same time. Never change the shared environment: no pip install, no npm install -g, no bench update, no bench setup, no bench get-app, and no install-app on any site except sellos_test.localhost and sellos_tenant_*.localhost. Never read, list or run anything under apps/buildos (~/iespl-bench/apps/buildos). To read BuildOS code, use only the read only reference copy at ~/iespl-baseline/buildos-reference, with ls, cat, grep and find, and never write, chmod, move or delete anything in it. The bench server on port 8000 and the sites pamaa and awh are not yours.

Rebuild from scratch (Jayman, 10 November 2026): build this task from its
own text. Do not assume the existing code is right. Read what is there,
replace what is weak, and keep what passes review against the task block.
Do not delete the tree first. Every task adds or refreshes tests that name
its task ID, even where code for it already exists.

$GUARD_RULES

$GUARDS_CHECK

MariaDB: never use the MariaDB root account or any root password. Tenant
sites are created, dropped, listed and probed only with
scripts/tenant-site.sh (create <id>, drop <id>, list, probe) or the
sellos.provisioning.tenant_sites module it runs, and code that needs the
provisioner password gets it only from
sellos.provisioning.credentials.get_provisioner_password(), which reads
the Keychain and hands the value to bench only through a child process's
environment. The account's name is in SELLOS_DB_PROVISIONER_USER. You do
not have the password and must never look for it: never run security
find-generic-password with -w (or any security command that prints a
secret), never print, echo, log or write the password, and never put it in
a file, a fixture, an exception message or a command line. If
get_provisioner_password() raises, reply NEEDS_INPUT with its message.

Styling: once docs/UI_STYLE.md exists, every new screen follows it (its
tokens, components and patterns) and never invents colors, spacing or fonts.

Respond with either of the following as the literal first characters
of your response, nothing before it:
IMPLEMENTATION_READY: <plain English summary of what you built>
NEEDS_INPUT: <plain English question>

Task:
$TASK_BLOCK"

  set +e
  RESPONSE="$(sellos_agent_env claude -p "$PROMPT" --dangerously-skip-permissions)"
  CLAUDE_EXIT=$?
  RESPONSE="$(sellos_redact_text "$RESPONSE")"
  set -e

  # Claude must not commit. If it did, take the commits back and keep the files in the working tree.
  if [[ "$(git rev-parse HEAD)" != "$IP_SHA" ]]; then
    echo "WARNING: Claude committed by itself. Taking its commits back and keeping its files for the gate."
    git log --format='  undone: %h %s' "$IP_SHA..HEAD" | cut -c1-120
    git reset --soft "$IP_SHA"
  fi

  # Keep every reply, and take the marker from whichever line carries it.
  mkdir -p "$LOG_DIR"
  printf '%s\n' "$RESPONSE" > "$LOG_DIR/claude-reply-${TASK_ID}-$(date +%Y%m%d-%H%M%S).txt"
  MARKER_LINE="$(printf '%s\n' "$RESPONSE" | grep -m1 -E '^(IMPLEMENTATION_READY|NEEDS_INPUT):' || true)"
  if [[ -n "$MARKER_LINE" ]]; then RESPONSE="$MARKER_LINE"; fi

  if is_limit "$RESPONSE"; then
    git add -A; loop_commit -m "$TASK_ID: salvage before waiting for the usage limit" --allow-empty >/dev/null 2>&1 || true
    git branch "failed/${TASK_ID}-limit-$(date +%Y%m%d-%H%M%S)" >/dev/null 2>&1 || true
    git reset --hard "$PRE_TASK_SHA" >/dev/null 2>&1; git clean -fd >/dev/null 2>&1
    wait_for_limit "$RESPONSE"
    continue
  fi
  if [[ "$CLAUDE_EXIT" -ne 0 ]]; then
    SALVAGE_BRANCH="failed/${TASK_ID}-$(date +%Y%m%d-%H%M%S)"
    git add -A
    loop_commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
    git branch "$SALVAGE_BRANCH" >/dev/null 2>&1 || true
    echo "Preserved this attempt's work on branch $SALVAGE_BRANCH before reverting main."
    git reset --hard "$PRE_TASK_SHA" && git clean -fd
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Blocked" "$TASKS_FILE"
    blocked_decide crash "Claude's process exited $CLAUDE_EXIT"
    git add "$TASKS_FILE"
    loop_commit -m "$TASK_ID: Claude process crashed, marking Blocked (repo reset to pre-task state)"
    "$SCRIPT_DIR/notify-telegram.sh" "$(blocked_notice "SellOS loop: $TASK_ID crashed Claude's process (exit $CLAUDE_EXIT). Marked Blocked, repo reset to before this task.")" || true
    [[ "$BLOCKED_STOP" -eq 1 ]] && break
    continue
  fi

  if [[ "$RESPONSE" == NEEDS_INPUT:* ]]; then
    SALVAGE_BRANCH="failed/${TASK_ID}-$(date +%Y%m%d-%H%M%S)"
    git add -A
    loop_commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
    git branch "$SALVAGE_BRANCH" >/dev/null 2>&1 || true
    echo "Preserved this attempt's work on branch $SALVAGE_BRANCH before reverting main."
    git reset --hard "$PRE_TASK_SHA" && git clean -fd
    stop_note needs-input "${RESPONSE#NEEDS_INPUT: }"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID needs input (repo reset to pre-task state) — ${RESPONSE#NEEDS_INPUT: }"
    break
  fi

  # A reply with no IMPLEMENTATION_READY label is not a failure by itself: if the work is in the folder, the gate decides.
  if [[ "$RESPONSE" != IMPLEMENTATION_READY:* && "$RESPONSE" != NEEDS_INPUT:* && -n "$(git status --short)" ]]; then
    echo "The reply had no IMPLEMENTATION_READY line, but the work is in the folder. Letting the gate decide."
    FIRST_LINE="$(printf '%s\n' "$RESPONSE" | grep -m1 -v '^[[:space:]]*$' | cut -c1-300)"
    RESPONSE="IMPLEMENTATION_READY: ${FIRST_LINE:-the work is done, the reply had no summary line}"
  fi

  if [[ "$RESPONSE" != IMPLEMENTATION_READY:* ]]; then
    SALVAGE_BRANCH="failed/${TASK_ID}-$(date +%Y%m%d-%H%M%S)"
    git add -A
    loop_commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
    git branch "$SALVAGE_BRANCH" >/dev/null 2>&1 || true
    echo "Preserved this attempt's work on branch $SALVAGE_BRANCH before reverting main."
    git reset --hard "$PRE_TASK_SHA" && git clean -fd
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Blocked" "$TASKS_FILE"
    blocked_decide unrecognized "the reply had no IMPLEMENTATION_READY or NEEDS_INPUT line and no work"
    git add "$TASKS_FILE"
    loop_commit -m "$TASK_ID: unrecognized response, marking Blocked (repo reset to pre-task state)"
    "$SCRIPT_DIR/notify-telegram.sh" "$(blocked_notice "SellOS loop: $TASK_ID gave an unrecognized response. Marked Blocked, repo reset to before this task.")" || true
    [[ "$BLOCKED_STOP" -eq 1 ]] && break
    continue
  fi

  SUMMARY="${RESPONSE#IMPLEMENTATION_READY: }"

  MAX_GATE_RUNS="${SELLOS_MAX_GATE_RUNS:-3}"
  GATE_RUN=1
  while true; do
    set +e
    mkdir -p "$LOG_DIR"
    run_gate_guarded
    TEST_EXIT=$?
    set -e
    if [[ "$TEST_EXIT" -eq 0 ]]; then break; fi
    # Exit 2 or 3: the gate stopped in its preflight and tested nothing (SOS-SETUP-14).
    if [[ "$TEST_EXIT" -eq 2 || "$TEST_EXIT" -eq 3 ]]; then
      stop_for_environment "The gate stopped before testing anything (exit $TEST_EXIT)." "$(tail -n 15 "$GATE_OUT")"
    fi
    # Exit 1. Before this failure may be repaired as code, or Block the task, the server must still
    # be SellOS. A server that died in the middle of a Cypress run must not be repaired as code.
    if only_connection_errors "$GATE_OUT"; then
      if ! PREFLIGHT_OUT="$(server_preflight)"; then
        stop_for_environment "Every failure in the gate's output was a connection error to the site, and the server preflight fails now." "$(grep -E "$CONNECTION_ERROR_RE" "$GATE_OUT" | head -n 5)
$PREFLIGHT_OUT"
      fi
      echo "Every failure was a connection error, but the server preflight passes now. Handling it as the task's failure."
    elif ! PREFLIGHT_OUT="$(server_preflight)"; then
      stop_for_environment "The gate failed, and the server preflight fails now (port, ping or the guest /sellos redirect), so the failure is not the code's." "$PREFLIGHT_OUT"
    fi
    if [[ "$GATE_RUN" -ge "$MAX_GATE_RUNS" ]]; then break; fi
    GATE_RUN=$((GATE_RUN + 1))
    echo "The gate failed. Asking Claude to repair it from the failure output (gate run $GATE_RUN of $MAX_GATE_RUNS)."
    FAILCTX="$(failure_context)"
    REPAIR_PROMPT="$(repair_head)$(affected_context)The test gate for the task below failed. Your changes are still in the working tree, uncommitted, and nothing has been reset. Read the failure output at the end, find the cause in the code, and fix it. This is gate run $GATE_RUN of $MAX_GATE_RUNS.
$GUARD_RULES
$GUARDS_CHECK
Rules. Fix the product code or the test you added, and never delete or weaken an assertion to make a test pass. A failing test is fixed in the code, not in the test, unless the task block says otherwise. Never use the MariaDB root account or a root password: only the provisioner account in SELLOS_DB_PROVISIONER_USER and SELLOS_DB_PROVISIONER_PASSWORD, whose values you never print, log or write. Never edit a gate file: scripts/run-tests.sh, scripts/build-loop.sh, scripts/watchdog.sh, scripts/select-next-task.sh, scripts/set-task-status.sh, scripts/make-baseline.sh, scripts/prepare-regression.sh, scripts/pause-loop.sh, scripts/resume-loop.sh, scripts/refresh-buildos-reference.sh, scripts/install-shared-helpers.sh, anything under scripts/shared, anything under scripts/lib, scripts/check_*.py, cypress.config.js, cypress/support/e2e.js, .pre-commit-config.yaml, .semgrepignore, .eslintrc, .github/workflows, docs/DEV_STRATEGY.md, docs/TESTING.md, docs/regression/README.md, scripts/check-guards.sh, sellos/testing/guards.py or docs/GUARDS.md, and never change the [tool.ruff] tables in pyproject.toml (adding a dependency there is fine). Never remove an assertion and never delete a test file. When you change a control or a test id, or what a form needs before it saves, grep cypress/ for it and update every spec that uses it, through one shared helper in cypress/support/commands.js where several specs do the same thing. If a failing test is in a file this task did not change, follow the policy below. Read the whole failing test first, because the first failing assertion hides every later one: check every assertion against the code before you reply, and fix all of them in this pass. You may run the single backend test module or the single browser spec that you changed, one at a time and in the foreground, from ~/iespl-bench: bench --site sellos_test.localhost run-tests --app sellos --module <dotted.module.path>, or bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/<path>. Never run the full suite, and never run anything in the background. Never run git commit, git push, git reset, git stash, git rebase, git merge, git checkout of another branch or set-task-status.sh, and never change a task's status: the loop does all of that after the gate passes. Leave your work uncommitted in the working tree. Never run seed_regression_data, any ui_fixtures.seed_* function or scripts/prepare-regression.sh, with bench execute or any other way: only prepare-regression.sh, run by a person, seeds the regression data. Check a seed change with a backend test that calls it and reads it back. The word Frappe must never appear in any user facing label, screen, or error message.
Policy, because nobody can answer questions during a run, so never ask one. If a failing test is outside this task, you may fix that test file or the shared fixtures it uses when the cause is test data, test order or a hard coded assumption, and you must say what you changed. If a test deletes or empties shared data, make it restore what it removed, even when it fails. Never change product code that this task did not touch just to make a test pass, and never weaken or delete an assertion. If you truly cannot fix it, still reply with IMPLEMENTATION_READY and a plain account of what is failing and why.
Respond with this as the literal first characters of your response, nothing before it:
IMPLEMENTATION_READY: <plain English summary of what you fixed>

Task:
$TASK_BLOCK

Failure output:
$FAILCTX"
    set +e
    REPAIR_RESPONSE="$(sellos_agent_env claude -p "$REPAIR_PROMPT" --dangerously-skip-permissions)"
    REPAIR_EXIT=$?
    REPAIR_RESPONSE="$(sellos_redact_text "$REPAIR_RESPONSE")"
    while is_limit "$REPAIR_RESPONSE"; do
      wait_for_limit "$REPAIR_RESPONSE"
      REPAIR_RESPONSE="$(sellos_agent_env claude -p "$REPAIR_PROMPT" --dangerously-skip-permissions)"
      REPAIR_EXIT=$?
      REPAIR_RESPONSE="$(sellos_redact_text "$REPAIR_RESPONSE")"
    done
    set -e
    mkdir -p "$LOG_DIR"
    printf '%s\n' "$REPAIR_RESPONSE" > "$LOG_DIR/claude-repair-${TASK_ID}-$(date +%Y%m%d-%H%M%S).txt"
    REPAIR_MARKER="$(printf '%s\n' "$REPAIR_RESPONSE" | grep -m1 -E '^IMPLEMENTATION_READY:' || true)"
    if [[ -z "$REPAIR_MARKER" && "$REPAIR_EXIT" -eq 0 ]] && printf '%s\n' "$REPAIR_RESPONSE" | grep -q -E '^NEEDS_INPUT:'; then
      echo "The repair step asked a question. Nobody can answer during a run, so it is told to decide for itself."
      QUESTION="$(printf '%s\n' "$REPAIR_RESPONSE" | head -c 3000)"
      set +e
      REPAIR_RESPONSE="$(sellos_agent_env claude -p "$REPAIR_PROMPT

Your previous reply was a question, and nobody can answer it during a run:
$QUESTION

Decide for yourself, following the policy above, and fix it now. Do not ask again." --dangerously-skip-permissions)"
      REPAIR_EXIT=$?
      REPAIR_RESPONSE="$(sellos_redact_text "$REPAIR_RESPONSE")"
      set -e
      printf '%s\n' "$REPAIR_RESPONSE" > "$LOG_DIR/claude-repair2-${TASK_ID}-$(date +%Y%m%d-%H%M%S).txt"
      REPAIR_MARKER="$(printf '%s\n' "$REPAIR_RESPONSE" | grep -m1 -E '^IMPLEMENTATION_READY:' || true)"
    fi
    if [[ "$REPAIR_EXIT" -ne 0 || -z "$REPAIR_MARKER" ]]; then break; fi
    SUMMARY="${REPAIR_MARKER#IMPLEMENTATION_READY: }"
  done

  if [[ "$TEST_EXIT" -eq 0 ]]; then
    BLOCKED_IN_A_ROW=0
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Complete" "$TASKS_FILE"
    git add -A
    # SOS-SETUP-22: the subject is "<TASK ID>: <task title>" and the agent's summary is the body, at
    # most 20 lines, wrapped at 100 characters.
    COMMIT_MSG_FILE="$LOG_DIR/commit-msg-$TASK_ID.txt"
    {
      printf '%s: %s\n\n' "$TASK_ID" "$TASK_TITLE"
      printf '%s\n' "$SUMMARY" | fold -s -w 100 | head -n 20
    } >"$COMMIT_MSG_FILE"
    loop_commit -F "$COMMIT_MSG_FILE"
    rm -f "$COMMIT_MSG_FILE"
    if ! push_with_retry; then
      stop_note push-failed "the push failed after every retry"
      "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID passed the gate and is committed, but the push failed after every retry. The commit is kept and nothing was reset. The next start pushes it first. Stopping. git said:
$(printf '%s' "$PUSH_ERROR" | head -c 3000)" || true
      break
    fi
    RUN_SUMMARY="$(python3 "$STOPS_PY" summary "$STOPS_FILE" "$PROJECT_DIR" 2>/dev/null || true)"
    echo "$RUN_SUMMARY"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID complete: $TASK_TITLE
$RUN_SUMMARY"
    if ! ci_until_green "the commit for $TASK_ID" "$TASK_ID"; then
      stop_note "$CI_STOP_CATEGORY" "$CI_STOP_CAUSE"
      ci_notify "$CI_STOP_NOTICE"
      break
    fi
  else
    TAIL="$(tail -n 40 "$LOG_DIR/latest.log" 2>/dev/null || echo 'no log available')"
    SALVAGE_BRANCH="failed/${TASK_ID}-$(date +%Y%m%d-%H%M%S)"
    git add -A
    loop_commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
    git branch "$SALVAGE_BRANCH" >/dev/null 2>&1 || true
    echo "Preserved this attempt's work on branch $SALVAGE_BRANCH before reverting main."
    git reset --hard "$PRE_TASK_SHA" && git clean -fd
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Blocked" "$TASKS_FILE"
    # SOS-SETUP-37: a gate that failed on specs the task did not change is its own category.
    BLOCK_CATEGORY=blocked
    if grep -q -E '^AFFECTED SPECS? FAILED' "$LOG_DIR/latest.log" 2>/dev/null; then BLOCK_CATEGORY="task broke older specs"; fi
    blocked_decide "$BLOCK_CATEGORY" "the gate still failed after $GATE_RUN gate run(s): $(grep -m1 -E "GUARDS FAILED|AFFECTED SPECS FAILED|CHANGED TEST FAILED|CHANGED SPEC FAILED|BACKEND TESTS FAILED|UI TESTS FAILED|SMOKE TESTS FAILED|TENANT TEMPLATE FAILED" "$LOG_DIR/latest.log" 2>/dev/null | cut -c1-120 || echo "see the gate log")"
    git add "$TASKS_FILE"
    loop_commit -m "$TASK_ID: tests failed, marking Blocked (repo reset to pre-task state, no broken code left on main)"
    "$SCRIPT_DIR/notify-telegram.sh" "$(blocked_notice "SellOS loop: $TASK_ID failed tests. Blocked, repo reset to before this task — main is clean. Tail: $TAIL")" || true
    [[ "$BLOCKED_STOP" -eq 1 ]] && break
    continue
  fi
done
