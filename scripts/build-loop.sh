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
# containers. If you want the loop to also restart/reload `bench start`
# (or `bench build` for JS assets) after every Complete so dev_site
# reflects the change live, tell me how bench is currently being run
# (foreground terminal, tmux/screen, or something else) and I'll add
# that step — restarting it wrong could kill your working dev session,
# so it's deliberately left out rather than guessed at.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TASKS_FILE="$PROJECT_DIR/TASKS.md"
LOCK_FILE="/tmp/sellos-build-loop.lock"
BRANCH="${SELLOS_BRANCH:-1.0}"

# Both loops restore databases and clear the cache on the same bench, so they must not overlap.
if pgrep -f "buildos/scripts/(run-tests|build-loop)\.sh" >/dev/null 2>&1; then
  echo "The BuildOS loop or gate is running on this bench. Wait for it to finish, then start this again."
  exit 1
fi

if [[ -f "$LOCK_FILE" ]]; then
  OLD_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Another build-loop.sh is already running (pid $OLD_PID) against this repo. Exiting."
    exit 1
  fi
  echo "Stale lock file found (pid ${OLD_PID:-unknown}, not running). Removing."
  rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

cd "$PROJECT_DIR"

# What went wrong in the last gate run: the unit test failures, the browser test failures, and the end of the log.
failure_context() {
  local log="/tmp/sellos-test-logs/latest.log"
  if [[ ! -f "$log" ]]; then log="$(ls -t /tmp/sellos-test-logs/run-*.log 2>/dev/null | head -1)"; fi
  if [[ -z "$log" || ! -f "$log" ]]; then echo "no log available"; return; fi
  local eq; eq="$(printf '=%.0s' $(seq 1 70))"
  {
    echo "--- unit test failures:"
    awk -v eq="$eq" '{L[NR]=$0} $0==eq{if (bs==0 || bs<prevran) bs=NR} /^Ran [0-9]+ tests/{prevran=NR} /^FAILED \(/{s=bs; e=NR} END{if (e) for (i=s;i<=e;i++) print L[i]}' "$log" | head -150
    echo "--- browser test failures:"
    awk '/^  [0-9]+\) /{c=14} c>0{print; c--}' "$log" | head -150
    echo "--- last lines of the run:"
    tail -n 25 "$log"
  } | cut -c1-220
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
ci_green() {
  local sha="$1" ids="" i=0 id rc=0
  while [[ $i -lt 12 && -z "$ids" ]]; do
    ids="$(gh run list --branch "$BRANCH" --commit "$sha" --json databaseId --jq '.[].databaseId' 2>/dev/null || true)"
    [[ -z "$ids" ]] && sleep 10
    i=$((i + 1))
  done
  if [[ -z "$ids" ]]; then echo "No CI run found for $sha."; return 1; fi
  sleep 20
  ids="$(gh run list --branch "$BRANCH" --commit "$sha" --json databaseId --jq '.[].databaseId' 2>/dev/null || echo "$ids")"
  for id in $ids; do
    gh run watch "$id" --exit-status >/dev/null 2>&1 || { echo "CI run $id failed."; rc=1; }
  done
  return $rc
}

while true; do
  TASK_ID="$("$SCRIPT_DIR/select-next-task.sh" "$TASKS_FILE")"

  if [[ "$TASK_ID" == "NONE_ELIGIBLE" ]]; then
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
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: halted. Blocked task(s) still open: ${TASK_ID#BLOCKED_EXISTS:}. Fix and reset to Not Started before any new work can start."
    break
  fi

  echo "Selected task: $TASK_ID"

  # Known-good point to fall back to if this task doesn't end cleanly.
  PRE_TASK_SHA="$(git rev-parse HEAD)"

  TASK_BLOCK="$(awk -v id="$TASK_ID" '
    $0 ~ "^### " id ":" { printing = 1; print; next }
    printing && /^### / { exit }
    printing { print }
  ' "$TASKS_FILE")"

  CURRENT_STATUS="$(printf '%s\n' "$TASK_BLOCK" | grep -m1 '\*\*Status:\*\*' | sed -E 's/.*\*\*Status:\*\* *//')"

  if [[ "$CURRENT_STATUS" == "Not Started" ]]; then
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "In Progress" "$TASKS_FILE"
    git add "$TASKS_FILE"
    git commit -m "$TASK_ID: mark In Progress"
  fi

  IP_SHA="$(git rev-parse HEAD)"

  PROMPT="You are implementing one task from SellOS's TASKS.md inside the
sellos Frappe v16 app. Never run the full test suite or the whole browser suite, and never run anything in the background. You may, and should, run the single backend test module and the single browser spec that you add or change, one at a time and in the foreground: for a module, from ~/iespl-bench, bench --site sellos_test.localhost run-tests --app sellos --module <dotted.module.path>; for a spec, from ~/iespl-bench, bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/<path>. Fix whatever fails before you reply. The loop then runs scripts/run-tests.sh separately and blocks on its real result. Never run git commit, git push, git reset, git stash, git rebase, git merge, git checkout of another branch or set-task-status.sh, and never change a task's status: the loop does all of that after the gate passes. Leave your work uncommitted in the working tree. A task whose block says Browser spec: required also adds its flows to docs/regression/flows.md, one line each in the form FLOW <task id>-<n> | role | start path | steps | expected result (see that file). Add flows, never remove or change one, and if the task adds data a person sees, add it to seed_regression_data in sellos/tests/ui_fixtures.py through the production API and update its docstring.
Follow SellOS's locked architecture: no ERPNext. The web app never uses
the Frappe desk, and every customer feature is built in the SellOS web
app. There are five roles: Platform Admin, Company Admin, Agent, Client
and Channel Partner. Every company is its own site and database, so
isolation is by site. The consent check runs before every dial and has no
override for any role. Calls placed from the 022 number are for service
and transactional purposes only, and a promotional call purpose is
refused. The word 'Frappe' must never appear in any user facing label,
screen, or error message.

Respond with either of the following as the literal first characters
of your response, nothing before it:
IMPLEMENTATION_READY: <plain English summary of what you built>
NEEDS_INPUT: <plain English question>

Task:
$TASK_BLOCK"

  set +e
  RESPONSE="$(claude -p "$PROMPT" --dangerously-skip-permissions)"
  CLAUDE_EXIT=$?
  set -e

  # Claude must not commit. If it did, take the commits back and keep the files in the working tree.
  if [[ "$(git rev-parse HEAD)" != "$IP_SHA" ]]; then
    echo "WARNING: Claude committed by itself. Taking its commits back and keeping its files for the gate."
    git log --format='  undone: %h %s' "$IP_SHA..HEAD" | cut -c1-120
    git reset --soft "$IP_SHA"
  fi

  # Keep every reply, and take the marker from whichever line carries it.
  mkdir -p /tmp/sellos-test-logs
  printf '%s\n' "$RESPONSE" > "/tmp/sellos-test-logs/claude-reply-${TASK_ID}-$(date +%Y%m%d-%H%M%S).txt"
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
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID gave an unrecognized response. Marked Blocked, repo reset to before this task. Stopping."
    break
  fi

  SUMMARY="${RESPONSE#IMPLEMENTATION_READY: }"

  # The gate runs the three task guards from these.
  printf '%s\n' "$TASK_BLOCK" > /tmp/sellos-task-block.md
  export SELLOS_TASK_ID="$TASK_ID"
  export SELLOS_BASE_SHA="$IP_SHA"
  export SELLOS_TASK_BLOCK_FILE=/tmp/sellos-task-block.md

  MAX_GATE_RUNS="${SELLOS_MAX_GATE_RUNS:-3}"
  GATE_RUN=1
  while true; do
    set +e
    "$SCRIPT_DIR/run-tests.sh"
    TEST_EXIT=$?
    set -e
    if [[ "$TEST_EXIT" -eq 0 ]]; then break; fi
    if [[ "$GATE_RUN" -ge "$MAX_GATE_RUNS" ]]; then break; fi
    GATE_RUN=$((GATE_RUN + 1))
    echo "The gate failed. Asking Claude to repair it from the failure output (gate run $GATE_RUN of $MAX_GATE_RUNS)."
    FAILCTX="$(failure_context)"
    REPAIR_PROMPT="The test gate for the task below failed. Your changes are still in the working tree, uncommitted, and nothing has been reset. Read the failure output at the end, find the cause in the code, and fix it. This is gate run $GATE_RUN of $MAX_GATE_RUNS.
Rules. Fix the product code or the test you added, and never delete or weaken an assertion to make a test pass. A failing test is fixed in the code, not in the test, unless the task block says otherwise. Never edit a gate file: scripts/run-tests.sh, scripts/build-loop.sh, scripts/watchdog.sh, scripts/select-next-task.sh, scripts/set-task-status.sh, scripts/make-baseline.sh, anything under scripts/lib, scripts/check_*.py, cypress.config.js, cypress/support/e2e.js, .pre-commit-config.yaml, .github/workflows or docs/DEV_STRATEGY.md and docs/TESTING.md. Never remove an assertion and never delete a test file. If a failing test is in a file this task did not change, follow the policy below. Read the whole failing test first, because the first failing assertion hides every later one: check every assertion against the code before you reply, and fix all of them in this pass. You may run the single backend test module or the single browser spec that you changed, one at a time and in the foreground, from ~/iespl-bench: bench --site sellos_test.localhost run-tests --app sellos --module <dotted.module.path>, or bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/<path>. Never run the full suite, and never run anything in the background. Never run git commit, git push, git reset, git stash, git rebase, git merge, git checkout of another branch or set-task-status.sh, and never change a task's status: the loop does all of that after the gate passes. Leave your work uncommitted in the working tree. The word Frappe must never appear in any user facing label, screen, or error message.
Respond with either of the following as the literal first characters of your response, nothing before it:
Policy, because nobody can answer questions during a run, so never ask one. If a failing test is outside this task, you may fix that test file or the shared fixtures it uses when the cause is test data, test order or a hard coded assumption, and you must say what you changed. If a test deletes or empties shared data, make it restore what it removed, even when it fails. Never change product code that this task did not touch just to make a test pass, and never weaken or delete an assertion. If you truly cannot fix it, still reply with IMPLEMENTATION_READY and a plain account of what is failing and why.
Respond with this as the literal first characters of your response, nothing before it:
IMPLEMENTATION_READY: <plain English summary of what you fixed>

Task:
$TASK_BLOCK

Failure output:
$FAILCTX"
    set +e
    REPAIR_RESPONSE="$(claude -p "$REPAIR_PROMPT" --dangerously-skip-permissions)"
    REPAIR_EXIT=$?
    while is_limit "$REPAIR_RESPONSE"; do
      wait_for_limit "$REPAIR_RESPONSE"
      REPAIR_RESPONSE="$(claude -p "$REPAIR_PROMPT" --dangerously-skip-permissions)"
      REPAIR_EXIT=$?
    done
    set -e
    mkdir -p /tmp/sellos-test-logs
    printf '%s\n' "$REPAIR_RESPONSE" > "/tmp/sellos-test-logs/claude-repair-${TASK_ID}-$(date +%Y%m%d-%H%M%S).txt"
    REPAIR_MARKER="$(printf '%s\n' "$REPAIR_RESPONSE" | grep -m1 -E '^IMPLEMENTATION_READY:' || true)"
    if [[ -z "$REPAIR_MARKER" && "$REPAIR_EXIT" -eq 0 ]] && printf '%s\n' "$REPAIR_RESPONSE" | grep -q -E '^NEEDS_INPUT:'; then
      echo "The repair step asked a question. Nobody can answer during a run, so it is told to decide for itself."
      QUESTION="$(printf '%s\n' "$REPAIR_RESPONSE" | head -c 3000)"
      set +e
      REPAIR_RESPONSE="$(claude -p "$REPAIR_PROMPT

Your previous reply was a question, and nobody can answer it during a run:
$QUESTION

Decide for yourself, following the policy above, and fix it now. Do not ask again." --dangerously-skip-permissions)"
      REPAIR_EXIT=$?
      set -e
      printf '%s\n' "$REPAIR_RESPONSE" > "/tmp/sellos-test-logs/claude-repair2-${TASK_ID}-$(date +%Y%m%d-%H%M%S).txt"
      REPAIR_MARKER="$(printf '%s\n' "$REPAIR_RESPONSE" | grep -m1 -E '^IMPLEMENTATION_READY:' || true)"
    fi
    if [[ "$REPAIR_EXIT" -ne 0 || -z "$REPAIR_MARKER" ]]; then break; fi
    SUMMARY="${REPAIR_MARKER#IMPLEMENTATION_READY: }"
  done

  if [[ "$TEST_EXIT" -eq 0 ]]; then
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Complete" "$TASKS_FILE"
    git add -A
    git commit -m "$TASK_ID: $SUMMARY"
    git push origin "$BRANCH"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID complete. $SUMMARY"
    if ! ci_green "$(git rev-parse HEAD)"; then
      "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: CI is red (or missing) on the commit for $TASK_ID. Stopping, nothing new started."
      break
    fi
  else
    TAIL="$(tail -n 40 /tmp/sellos-test-logs/latest.log 2>/dev/null || echo 'no log available')"
    SALVAGE_BRANCH="failed/${TASK_ID}-$(date +%Y%m%d-%H%M%S)"
    git add -A
    git commit -m "$TASK_ID: salvage before revert (may not build or pass tests)" --allow-empty >/dev/null 2>&1 || true
    git branch "$SALVAGE_BRANCH" >/dev/null 2>&1 || true
    echo "Preserved this attempt's work on branch $SALVAGE_BRANCH before reverting main."
    git reset --hard "$PRE_TASK_SHA" && git clean -fd
    "$SCRIPT_DIR/set-task-status.sh" "$TASK_ID" "Blocked" "$TASKS_FILE"
    git add "$TASKS_FILE"
    git commit -m "$TASK_ID: tests failed, marking Blocked (repo reset to pre-task state, no broken code left on main)"
    "$SCRIPT_DIR/notify-telegram.sh" "SellOS loop: $TASK_ID failed tests. Blocked, repo reset to before this task — main is clean. Tail: $TAIL"
    break
  fi
done
