#!/usr/bin/env bash
# transcript_leak.sh — the gate's check of Claude Code transcripts for a loop secret.
#
# A secret in a transcript of an INTERACTIVE session is an environment fault, not a task's: the
# value is overwritten in place (same length), Telegram is told which file and variable (never the
# value), and the gate stops with exit 3 through sellos_env_exit, so no task is repaired or Blocked.
# A loop agent's own transcript is an ordinary leak: exit 1.
#   sellos_transcript_leak_check <since epoch> <transcripts dir>
sellos_transcript_leak_check() {
  local since="$1" dir="$2" lib status=0 out
  lib="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  out="$(python3 "$lib/check_no_secret_leak.py" --since "$since" --transcripts "$dir")" || status=$?
  printf '%s\n' "$out"
  if [ "$status" -eq 3 ]; then
    "$lib/notify-telegram.sh" "SellOS environment fault: a secret was found in an interactive session transcript and overwritten in place. Not a task failure. $(printf '%s\n' "$out" | grep '^  ' | sed -E 's#/[^ ]*/##' | tr '\n' ';')" || true
    sellos_env_exit 3
  elif [ "$status" -ne 0 ]; then
    exit "$status"
  fi
}
