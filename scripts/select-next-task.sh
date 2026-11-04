#!/usr/bin/env bash
# select-next-task.sh — pick the next eligible task from TASKS.md.
# Prints a task ID, or NONE_ELIGIBLE if nothing can be worked on right now.
#
# Usage: select-next-task.sh [TASKS_FILE]   (defaults to ./TASKS.md)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASKS_FILE="${1:-TASKS.md}"

if [[ ! -f "$TASKS_FILE" ]]; then
  echo "NONE_ELIGIBLE"
  exit 0
fi

python3 "$SCRIPT_DIR/lib/tasks.py" select "$TASKS_FILE"
