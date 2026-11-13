#!/usr/bin/env bash
# build-loop.sh — the SellOS autonomous build loop.
#
# Run this from the sellos app repo (or anywhere — it locates
# itself relative to this script's own path). Each cycle:
#   1. Pick the next task (select-next-task.sh).
#   2. Mark it In Progress and commit that immediately.
#   3. Call `claude -p` once with the task embedded in the prompt.
#   4. On IMPLEMENTATION_READY: run the real test gate (run-tests.sh).
#      Pass -> mark Complete, commit, push. Fail -> mark Blocked, stop.
#   5. On NEEDS_INPUT: notify and stop — a human needs to answer.
#   6. On a crashed Claude process: mark Blocked, notify, stop.
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
# The loop stops itself on any blocked/needs-input/no-work state. It is
# not designed to grind through failures unattended — that's deliberate,
# per the OTT build's own experience.
#
# HARD RULE: development does not progress while anything is Blocked.
# select-next-task.sh (via tasks.py) refuses to pick new "Not Started"
# work as long as any task's Status is Blocked — it returns
# "BLOCKED_EXISTS:<id,id,...>" instead, and this script treats that as
# an immediate stop, same as a crash. A Blocked task is never
# auto-resumed either. Root-cause the failure, verify it by hand
# (including actually browsing the result, not just re-reading logs),
# then run `scripts/set-task-status.sh <TASK_ID> "Not Started"`
# yourself before relaunching.
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

# SOS-SETUP-33: the stop ledger. Every way this script ends, except "another loop is running", appends
# one row to docs/STOPS.md (time, task, category, cause, minutes the attempt took) through the EXIT
# trap, and prints the hours since the last stop. The next start commits the row with the idle time. Each stop site sets its category and
# cause with stop_note first; anything that ends the loop without one (set -e, a signal) is still
# recorded, as "unexpected" or "stopped". The next start fills in how long the loop stood idle.
STOPS_FILE="$PROJECT_DIR/docs/STOPS.md"
STOPS_PY="$SCRIPT_DIR/lib/stops.py"
STOP_CATEGORY="unexpected"
STOP_CAUSE="the loop ended without saying why (a failed command under set -e)"
STOP_TASK="-"
stop_note() { STOP_CATEGORY="$1"; STOP_CAUSE="$2"; }
on_exit() {
  local status=$? minutes=0
  if [[ "$(cat "$LOCK_FILE" 2>/dev/null)" == "$$" ]]; then rm -f "$LOCK_FILE"; fi
  [[ "$STOP_CATEGORY" == "none" ]] && return
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
    git -C "$PROJECT_DIR" commit -q -m "SOS-LOOP: the last stop and the restart, in docs/STOPS.md [skip ci]" -- docs/STOPS.md || true
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
ci_green() {
  local sha="$1" ids="" i=0 id rc=0 unstarted
  CI_RED_REASON=""
  while [[ $i -lt 12 && -z "$ids" ]]; do
    ids="$(gh run list --branch "$BRANCH" --commit "$sha" --json databaseId --jq '.[].databaseId' 2>/dev/null || true)"
    [[ -z "$ids" ]] && sleep 10
    i=$((i + 1))
  done
  if [[ -z "$ids" ]]; then echo "No CI run found for $sha."; return 1; fi
  sleep 20
  ids="$(gh run list --branch "$BRANCH" --commit "$sha" --json databaseId --jq '.[].databaseId' 2>/dev/null || echo "$ids")"
  for id in $ids; do
    if ! gh run watch "$id" --exit-status >/dev/null 2>&1; then
      echo "CI run $id failed."
      rc=1
      unstarted="$(python3 "$SCRIPT_DIR/lib/ci_minutes.py" never-started "$id" 2>/dev/null || true)"
      if [[ -n "$unstarted" ]]; then
        CI_RED_REASON="CI run $id: these jobs never started ($unstarted). The Actions minutes budget may be spent, or billing needs attention. This is not a code failure."
        echo "$CI_RED_REASON"
      fi
    fi
  done
  return $rc
}

# Push the branch. A failed try is retried after 10, 30 and 90 seconds. GitHub's own
# "fatal error in commit_refs" is a server fault, so it is retried like a network error,
# never treated as a rejection. A real rejection stops at once, because retrying cannot fix it.
# On failure PUSH_ERROR holds git's exact output. Nothing here ever resets a commit.
PUSH_ERROR=""
push_with_retry() {
  local waits=(10 30 90) attempt=0 out
  PUSH_ERROR=""
  while true; do
    if out="$(git push origin "$BRANCH" 2>&1)"; then
      printf '%s\n' "$out"
      return 0
    fi
    printf '%s\n' "$out"
    PUSH_ERROR="$out"
    if printf '%s\n' "$out" | grep -q "fatal error in commit_refs"; then
      echo "The push failed with \"fatal error in commit_refs\". That is an error on GitHub's side, not a rejected push. Retrying."
    elif printf '%s\n' "$out" | grep -q -E "\[rejected\]|\[remote rejected\]|non-fast-forward|fetch first"; then
      echo "The remote rejected the push. Retrying will not fix that."
      return 1
    fi
    if [[ $attempt -ge ${#waits[@]} ]]; then return 1; fi
    echo "Push failed. Trying again in ${waits[$attempt]} seconds."
    sleep "${waits[$attempt]}"
    attempt=$((attempt + 1))
  done
}

# SOS-SETUP-14: an environment problem is not a task failure. The gate exits 2 or 3 only from its
# preflight (wrong site or port, a server that is down or is not SellOS, no baseline, no Semgrep,
# another gate running), never because of the task's code: run-tests.sh maps every other failure to
# 1. A server that dies in the middle of a Cypress run makes the gate exit 1, so after every failed
# gate run the loop runs the gate's own server preflight again (scripts/lib/sellos_server.sh: the
# port, ping, and the guest /sellos redirect). If it fails, the failure is the environment's.
BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
TEST_SITE="${SELLOS_TEST_SITE:-sellos_test.localhost}"
GATE_OUT="$LOG_DIR/loop-gate-output.txt"
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
SUMMARY_LINE_RE='FAILED \(|FAILED AGAIN|SPEC FAILED|UI tests failed|Failing:|[0-9]+ of [0-9]+ failed|│|GATE PASSED'

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
AHEAD="$(git rev-list --count "origin/$BRANCH..$BRANCH" 2>/dev/null || echo 0)"
if [[ "$AHEAD" -gt 0 ]]; then
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
  echo "$BRANCH is $AHEAD commit(s) ahead of origin. Pushing them before any task starts:"
  printf '%s\n' "$AHEAD_LIST"
  if ! push_with_retry; then
    stop_note push-failed "pushing the commits that were ahead failed"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $BRANCH is $AHEAD commit(s) ahead of origin and the push failed. Stopping before any task starts. The commits are kept:
$AHEAD_LIST
git said:
$(printf '%s' "$PUSH_ERROR" | head -c 3000)" || true
    exit 1
  fi
  # SOS-SETUP-33: a push of nothing but the stop ledger ([skip ci]) changes no code, so CI is not run or awaited.
  if [[ -z "$(printf '%s\n' "$AHEAD_LIST" | awk '$2 != "SOS-LOOP:"')" ]]; then
    echo "Only the stop ledger was ahead. Pushed it without waiting for CI."
  else
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: pushed $AHEAD commit(s) that were ahead of origin. Waiting for CI before picking a task:
$AHEAD_LIST" || true
    if ! ci_green "$(git rev-parse HEAD)"; then
      stop_note ci-red "CI red or missing on the pushed head. $CI_RED_REASON"
      "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: CI is red (or missing) on the pushed head $(git rev-parse --short HEAD). Stopping, nothing new started.${CI_RED_REASON:+ $CI_RED_REASON}" || true
      exit 1
    fi
  fi
fi

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

  if [[ "$TASK_ID" == BLOCKED_EXISTS:* ]]; then
    stop_note blocked-exists "a Blocked task is open: ${TASK_ID#BLOCKED_EXISTS:}"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: halted. Blocked task(s) still open: ${TASK_ID#BLOCKED_EXISTS:}. Fix and reset to Not Started before any new work can start."
    break
  fi

  echo "Selected task: $TASK_ID"
  STOP_TASK="$TASK_ID"

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
    git commit -m "$TASK_ID: mark In Progress"
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
sellos Frappe v16 app. Never run the full test suite or the whole browser suite, and never run anything in the background. Never start, stop or touch the servers on port 8000 (BuildOS) or 8002 (Pamaa); SellOS runs only on port 8004, on the server Jayman starts with cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004. You may, and should, run the single backend test module and the single browser spec that you add or change, one at a time and in the foreground: for a module, from ~/iespl-bench, bench --site sellos_test.localhost run-tests --app sellos --module <dotted.module.path>; for a spec, from ~/iespl-bench, bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/<path>. Fix whatever fails before you reply. The loop then runs scripts/run-tests.sh separately and blocks on its real result. Never run git commit, git push, git reset, git stash, git rebase, git merge, git checkout of another branch or set-task-status.sh, and never change a task's status: the loop does all of that after the gate passes. Leave your work uncommitted in the working tree. A task whose block says Browser spec: required also adds its flows to docs/regression/flows.md, one line each in the form FLOW <task id>-<n> | role | start path | steps | expected result (see that file). Add flows, never remove or change one, and if the task adds data a person sees, add it to seed_regression_data in sellos/tests/ui_fixtures.py through the production API and update its docstring.
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
    git add -A; git commit -m "$TASK_ID: salvage before waiting for the usage limit" --allow-empty >/dev/null 2>&1 || true
    git branch "failed/${TASK_ID}-limit-$(date +%Y%m%d-%H%M%S)" >/dev/null 2>&1 || true
    git reset --hard "$PRE_TASK_SHA" >/dev/null 2>&1; git clean -fd >/dev/null 2>&1
    wait_for_limit "$RESPONSE"
    continue
  fi
  if [[ "$CLAUDE_EXIT" -ne 0 ]]; then
    SALVAGE_BRANCH="failed/${TASK_ID}-$(date +%Y%m%d-%H%M%S)"
    git add -A
    git commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
    git branch "$SALVAGE_BRANCH" >/dev/null 2>&1 || true
    echo "Preserved this attempt's work on branch $SALVAGE_BRANCH before reverting main."
    git reset --hard "$PRE_TASK_SHA" && git clean -fd
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Blocked" "$TASKS_FILE"
    git add "$TASKS_FILE"
    git commit -m "$TASK_ID: Claude process crashed, marking Blocked (repo reset to pre-task state)"
    stop_note crash "Claude's process exited $CLAUDE_EXIT"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID crashed Claude's process (exit $CLAUDE_EXIT). Marked Blocked, repo reset to before this task. Stopping."
    break
  fi

  if [[ "$RESPONSE" == NEEDS_INPUT:* ]]; then
    SALVAGE_BRANCH="failed/${TASK_ID}-$(date +%Y%m%d-%H%M%S)"
    git add -A
    git commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
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
    git commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
    git branch "$SALVAGE_BRANCH" >/dev/null 2>&1 || true
    echo "Preserved this attempt's work on branch $SALVAGE_BRANCH before reverting main."
    git reset --hard "$PRE_TASK_SHA" && git clean -fd
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Blocked" "$TASKS_FILE"
    git add "$TASKS_FILE"
    git commit -m "$TASK_ID: unrecognized response, marking Blocked (repo reset to pre-task state)"
    stop_note unrecognized "the reply had no IMPLEMENTATION_READY or NEEDS_INPUT line and no work"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID gave an unrecognized response. Marked Blocked, repo reset to before this task. Stopping."
    break
  fi

  SUMMARY="${RESPONSE#IMPLEMENTATION_READY: }"

  MAX_GATE_RUNS="${SELLOS_MAX_GATE_RUNS:-3}"
  GATE_RUN=1
  while true; do
    set +e
    mkdir -p "$LOG_DIR"
    "$SCRIPT_DIR/run-tests.sh" 2>&1 | sellos_redact | tee "$GATE_OUT"
    TEST_EXIT="${PIPESTATUS[0]}"
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
    REPAIR_PROMPT="$(repair_head)The test gate for the task below failed. Your changes are still in the working tree, uncommitted, and nothing has been reset. Read the failure output at the end, find the cause in the code, and fix it. This is gate run $GATE_RUN of $MAX_GATE_RUNS.
$GUARD_RULES
$GUARDS_CHECK
Rules. Fix the product code or the test you added, and never delete or weaken an assertion to make a test pass. A failing test is fixed in the code, not in the test, unless the task block says otherwise. Never use the MariaDB root account or a root password: only the provisioner account in SELLOS_DB_PROVISIONER_USER and SELLOS_DB_PROVISIONER_PASSWORD, whose values you never print, log or write. Never edit a gate file: scripts/run-tests.sh, scripts/build-loop.sh, scripts/watchdog.sh, scripts/select-next-task.sh, scripts/set-task-status.sh, scripts/make-baseline.sh, scripts/prepare-regression.sh, scripts/pause-loop.sh, scripts/resume-loop.sh, scripts/refresh-buildos-reference.sh, scripts/install-shared-helpers.sh, anything under scripts/shared, anything under scripts/lib, scripts/check_*.py, cypress.config.js, cypress/support/e2e.js, .pre-commit-config.yaml, .semgrepignore, .eslintrc, .github/workflows, docs/DEV_STRATEGY.md, docs/TESTING.md, docs/regression/README.md, scripts/check-guards.sh, sellos/testing/guards.py or docs/GUARDS.md, and never change the [tool.ruff] tables in pyproject.toml (adding a dependency there is fine). Never remove an assertion and never delete a test file. If a failing test is in a file this task did not change, follow the policy below. Read the whole failing test first, because the first failing assertion hides every later one: check every assertion against the code before you reply, and fix all of them in this pass. You may run the single backend test module or the single browser spec that you changed, one at a time and in the foreground, from ~/iespl-bench: bench --site sellos_test.localhost run-tests --app sellos --module <dotted.module.path>, or bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/<path>. Never run the full suite, and never run anything in the background. Never run git commit, git push, git reset, git stash, git rebase, git merge, git checkout of another branch or set-task-status.sh, and never change a task's status: the loop does all of that after the gate passes. Leave your work uncommitted in the working tree. The word Frappe must never appear in any user facing label, screen, or error message.
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
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Complete" "$TASKS_FILE"
    git add -A
    # SOS-SETUP-22: the subject is "<TASK ID>: <task title>" and the agent's summary is the body, at
    # most 20 lines, wrapped at 100 characters.
    COMMIT_MSG_FILE="$LOG_DIR/commit-msg-$TASK_ID.txt"
    {
      printf '%s: %s\n\n' "$TASK_ID" "$TASK_TITLE"
      printf '%s\n' "$SUMMARY" | fold -s -w 100 | head -n 20
    } >"$COMMIT_MSG_FILE"
    git commit -F "$COMMIT_MSG_FILE"
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
    if ! ci_green "$(git rev-parse HEAD)"; then
      stop_note ci-red "CI red or missing on the task commit. $CI_RED_REASON"
      "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: CI is red (or missing) on the commit for $TASK_ID. Stopping, nothing new started.${CI_RED_REASON:+ $CI_RED_REASON}"
      break
    fi
  else
    TAIL="$(tail -n 40 "$LOG_DIR/latest.log" 2>/dev/null || echo 'no log available')"
    SALVAGE_BRANCH="failed/${TASK_ID}-$(date +%Y%m%d-%H%M%S)"
    git add -A
    git commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
    git branch "$SALVAGE_BRANCH" >/dev/null 2>&1 || true
    echo "Preserved this attempt's work on branch $SALVAGE_BRANCH before reverting main."
    git reset --hard "$PRE_TASK_SHA" && git clean -fd
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Blocked" "$TASKS_FILE"
    git add "$TASKS_FILE"
    git commit -m "$TASK_ID: tests failed, marking Blocked (repo reset to pre-task state, no broken code left on main)"
    stop_note blocked "the gate still failed after $GATE_RUN gate run(s): $(grep -m1 -E "GUARDS FAILED|CHANGED TEST FAILED|CHANGED SPEC FAILED|BACKEND TESTS FAILED|UI TESTS FAILED|TENANT TEMPLATE FAILED" "$LOG_DIR/latest.log" 2>/dev/null || echo "see the gate log")"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID failed tests. Blocked, repo reset to before this task — main is clean. Tail: $TAIL"
    break
  fi
done
