#!/usr/bin/env bash
# bench-gate-lock.sh: one lock for the heavy segment of every gate on ~/iespl-bench (SOS-SETUP-20).
#
# BuildOS and SellOS loops run at the same time on one bench. Their sites do not collide (Redis keys
# are namespaced per site and bench clear-cache is per site), but two baseline restores, migrations and
# Cypress runs at once starve each other. So each gate takes this lock from its baseline restore to the
# end of its Cypress run, and nothing else is serialised.
#
# The canonical copy is apps/sellos/scripts/shared/bench-gate-lock.sh. scripts/install-shared-helpers.sh
# installs it to ~/iespl-baseline/bench-gate-lock.sh, outside both repositories, where every gate
# sources it (SOS-SETUP-21). Edit the repository copy, never the installed one. Bash 3.2 compatible.
#
#   source ~/iespl-baseline/bench-gate-lock.sh
#   bench_gate_acquire <owner> [max_wait_seconds]   # default 5400; exit 3 after it
#   ...heavy work...
#   bench_gate_release                              # also runs on EXIT, INT and TERM
#
# The lock is the directory /tmp/iespl-bench-heavy.lock.d holding the files owner, pid and start.
# A waiter polls every 5 seconds and prints "Waiting for <owner> (pid N, running Xm)". A lock whose
# pid is dead, or that is older than 2 hours, is stale and is stolen with a warning. A wait longer
# than 30 minutes is notified once, through the command in BENCH_GATE_NOTIFY (given the message as
# its one argument), if it is set.
#
# Overrides, for tests: BENCH_GATE_LOCK_DIR, BENCH_GATE_POLL, BENCH_GATE_STALE_AFTER,
# BENCH_GATE_NOTIFY_AFTER, BENCH_GATE_PID (the pid recorded as the holder; default the pid of the shell
# that calls bench_gate_acquire, which is a subshell's own pid when called inside one, not $$).
# After a successful acquire, BENCH_GATE_WAITED holds the seconds waited.

BENCH_GATE_LOCK_DIR="${BENCH_GATE_LOCK_DIR:-/tmp/iespl-bench-heavy.lock.d}"
BENCH_GATE_POLL="${BENCH_GATE_POLL:-5}"
BENCH_GATE_STALE_AFTER="${BENCH_GATE_STALE_AFTER:-7200}"
BENCH_GATE_NOTIFY_AFTER="${BENCH_GATE_NOTIFY_AFTER:-1800}"
BENCH_GATE_HELD=""
BENCH_GATE_WAITED=0

_bench_gate_read() {
  cat "$BENCH_GATE_LOCK_DIR/$1" 2>/dev/null || true
}

# The pid defaults to the calling shell itself. $$ is the script's pid even inside a subshell, and
# bash 3.2 has no BASHPID, so there a child prints its parent's pid.
_bench_gate_try() {
  # mkdir is atomic: exactly one caller creates the directory.
  mkdir "$BENCH_GATE_LOCK_DIR" 2>/dev/null || return 1
  printf '%s\n' "$1" >"$BENCH_GATE_LOCK_DIR/owner"
  printf '%s\n' "$2" >"$BENCH_GATE_LOCK_DIR/pid"
  printf '%s\n' "$3" >"$BENCH_GATE_LOCK_DIR/start"
  return 0
}

bench_gate_acquire() {
  local owner="${1:?bench_gate_acquire needs an owner}"
  local max_wait="${2:-5400}"
  local pid="${BENCH_GATE_PID:-}"
  local began now waited held_owner held_pid held_start age notified=""
  if [ -z "$pid" ]; then
    if [ -n "${BASHPID:-}" ]; then pid="$BASHPID"; else
      local f
      f="$(mktemp "${TMPDIR:-/tmp}/bench-gate-pid.XXXXXX")"
      sh -c 'echo $PPID' >"$f"
      pid="$(cat "$f")"
      rm -f "$f"
    fi
  fi
  began="$(date +%s)"
  while true; do
    now="$(date +%s)"
    if _bench_gate_try "$owner" "$pid" "$now"; then
      BENCH_GATE_HELD="$pid:$now"
      BENCH_GATE_WAITED=$((now - began))
      trap 'bench_gate_release' EXIT
      trap 'bench_gate_release; exit 130' INT
      trap 'bench_gate_release; exit 143' TERM
      echo "Bench gate lock taken by $owner (pid $pid) after waiting ${BENCH_GATE_WAITED}s."
      return 0
    fi
    held_owner="$(_bench_gate_read owner)"
    held_pid="$(_bench_gate_read pid)"
    held_start="$(_bench_gate_read start)"
    case "$held_start" in '' | *[!0-9]*) held_start="$now" ;; esac
    age=$((now - held_start))
    if [ -z "$held_pid" ] || ! kill -0 "$held_pid" 2>/dev/null || [ "$age" -gt "$BENCH_GATE_STALE_AFTER" ]; then
      if [ -n "$held_pid" ] || [ -n "$held_owner" ]; then
        echo "WARNING: stealing a stale bench gate lock from ${held_owner:-unknown} (pid ${held_pid:-unknown}, $((age / 60))m old, holder dead or older than $((BENCH_GATE_STALE_AFTER / 60))m)." >&2
      fi
      rm -rf "$BENCH_GATE_LOCK_DIR"
      continue
    fi
    waited=$((now - began))
    if [ "$waited" -ge "$max_wait" ]; then
      echo "Gave up waiting for the bench gate lock after $((waited / 60))m (${waited}s): ${held_owner:-unknown} (pid $held_pid) has held it for $((age / 60))m. Check what it is doing, then run this again." >&2
      exit 3
    fi
    if [ -z "$notified" ] && [ "$waited" -ge "$BENCH_GATE_NOTIFY_AFTER" ]; then
      notified=1
      if [ -n "${BENCH_GATE_NOTIFY:-}" ]; then
        "$BENCH_GATE_NOTIFY" "$owner has waited $((waited / 60))m for the bench gate lock, held by ${held_owner:-unknown} (pid $held_pid, running $((age / 60))m)." >/dev/null 2>&1 || true
      fi
    fi
    echo "Waiting for ${held_owner:-unknown} (pid $held_pid, running $((age / 60))m)"
    sleep "$BENCH_GATE_POLL"
  done
}

bench_gate_release() {
  # Only the holder removes the lock: the pid and start time must still be the ones it wrote.
  if [ -n "$BENCH_GATE_HELD" ] && [ "$(_bench_gate_read pid):$(_bench_gate_read start)" = "$BENCH_GATE_HELD" ]; then
    rm -rf "$BENCH_GATE_LOCK_DIR"
    echo "Bench gate lock released."
  fi
  BENCH_GATE_HELD=""
  trap - EXIT INT TERM
}
