#!/usr/bin/env bash
# set-task-status.sh — update one task's Status line in TASKS.md.
#
# Usage: set-task-status.sh <TASK_ID> <NEW_STATUS> [TASKS_FILE]
# Example: set-task-status.sh SOS-P1-06 "In Progress"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TASK_ID="${1:?Usage: set-task-status.sh <TASK_ID> <NEW_STATUS> [TASKS_FILE]}"
NEW_STATUS="${2:?Missing new status}"
TASKS_FILE="${3:-TASKS.md}"

python3 "$SCRIPT_DIR/lib/tasks.py" set-status "$TASKS_FILE" "$TASK_ID" "$NEW_STATUS"
