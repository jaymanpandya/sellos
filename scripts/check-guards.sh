#!/usr/bin/env bash
# check-guards.sh: every cheap guard, in under 30 seconds, with no database and no bench (SOS-SETUP-33).
#
#   scripts/check-guards.sh          the files changed since the base commit (the agent, before it finishes)
#   scripts/check-guards.sh --all    every file, with CI's exact lint and Semgrep commands (the gate and CI)
#
# The base commit is SELLOS_BASE_SHA when the loop set it, else HEAD. The task guards (gate files,
# task evidence) need SELLOS_TASK_ID, SELLOS_BASE_SHA and SELLOS_TASK_BLOCK_FILE, which the loop
# exports before it calls the agent; a hand run without them skips those two and says so.
#
# Each guard that fails prints a block the loop hands to the repair agent first:
#   GUARD FAILED: <name>
#   Fix: <what is wrong and the fix the guard names>
#   END GUARD
# Every guard runs, so one run shows every failure. Exit 0 when all pass, 1 when any fails, and 3
# when a tool is missing (an environment problem, not the code's). docs/GUARDS.md explains each one.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE_DIR="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}"
SEMGREP="${SELLOS_SEMGREP:-$BASELINE_DIR/semgrep-venv/bin/semgrep}"
SEMGREP_RULES="${SELLOS_SEMGREP_RULES:-$BASELINE_DIR/semgrep-rules/rules}"
ALL=0
for arg in "$@"; do
  case "$arg" in
    --all) ALL=1 ;;
    -h | --help) sed -n 2,16p "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg (use --all or nothing)" >&2; exit 2 ;;
  esac
done
cd "$REPO_DIR" || exit 3

START="$(date +%s)"
FAILED=()
MISSING=()
BASE="${SELLOS_BASE_SHA:-$(git rev-parse HEAD)}"

guard_fail() { # name, fix text, details
  FAILED+=("$1")
  echo "GUARD FAILED: $1"
  echo "Fix: $2"
  [ -n "${3:-}" ] && printf '%s\n' "$3"
  echo "END GUARD"
}

# New files are seen by every check below, as CI sees them: mark them intent-to-add (no content staged).
git ls-files --others --exclude-standard -z | xargs -0 git add --intent-to-add 2>/dev/null || true

# Changed files: everything that differs from the base commit, new files included, deleted ones left out.
CHANGED=()
while IFS= read -r f; do
  [ -n "$f" ] && [ -f "$f" ] && CHANGED+=("$f")
done < <({ git diff --name-only "$BASE"; git ls-files --others --exclude-standard; } | sort -u)

if [ "$ALL" -eq 1 ]; then
  echo "=== Guards: every file (base ${BASE:0:9}) ==="
else
  echo "=== Guards: ${#CHANGED[@]} changed file(s) since ${BASE:0:9} ==="
fi

# 1 and 2. Raw phone numbers and commands outside sellos/provisioning (sellos/testing/guards.py).
for g in phones commands; do
  out="$(python3 -c 'import sys; sys.path.insert(0, "."); from sellos.testing import guards; sys.exit(guards.main(sys.argv[1:]))' "$g" 2>&1)"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "$out"
  else
    # guards.py prints the GUARD FAILED block itself.
    FAILED+=("$g")
    echo "$out"
  fi
done

# 3. Secrets: no loop secret value in the repository (the values come from the environment; with
# none set there is nothing to find). gitleaks runs in the lint step below.
if ! out="$(python3 scripts/check_no_secret_leak.py "$REPO_DIR" 2>&1)"; then
  guard_fail secrets "Remove the secret from the file named below and never write one: secrets live in the Keychain, site_config.json or the environment (CLAUDE.md, Secrets)." "$out"
else
  echo "Guard secrets: clean."
fi

# 4. Gate files (only with a task block: a human edits gate files by hand).
if [ -n "${SELLOS_TASK_ID:-}" ] && [ -n "${SELLOS_TASK_BLOCK_FILE:-}" ] && [ -f "${SELLOS_TASK_BLOCK_FILE:-}" ]; then
  if ! out="$(python3 scripts/check_gate_files.py "$BASE" "$SELLOS_TASK_BLOCK_FILE" 2>&1)"; then
    guard_fail gate-files "Put the files named below back as they were (git diff $BASE -- <file> shows your change). A task never changes what judges it; fix the code instead." "$out"
  else
    echo "Guard gate-files: $out"
  fi
else
  echo "Guard gate-files: skipped, no task is set (a hand run)."
fi

# 5. Assertion ratchet: no test file deleted, no assertion count lower than at the base.
if ! out="$(python3 scripts/check_assertion_ratchet.py "$BASE" 2>&1)"; then
  guard_fail assertion-ratchet "Put back every assertion and test file named below. Fix the code so the test passes, never the test." "$out"
else
  echo "Guard assertion-ratchet: clean."
fi

# 6. Task evidence: a new or changed test names the task (and a spec and flows when Browser spec: required).
if [ -n "${SELLOS_TASK_ID:-}" ] && [ -f "${SELLOS_TASK_BLOCK_FILE:-}" ]; then
  if ! out="$(python3 scripts/check_task_evidence.py "$SELLOS_TASK_ID" "$BASE" "$SELLOS_TASK_BLOCK_FILE" 2>&1)"; then
    guard_fail task-evidence "Add or refresh a test that names $SELLOS_TASK_ID in its class docstring or context() title and asserts the acceptance criteria." "$out"
  else
    echo "Guard task-evidence: $out"
  fi
else
  echo "Guard task-evidence: skipped, no task is set (a hand run)."
fi

# 7. Skipped specs wait for an unfinished task.
if ! out="$(python3 scripts/check_no_stale_skips.py ${SELLOS_TASK_ID:+--current "$SELLOS_TASK_ID"} TASKS.md cypress/integration 2>&1)"; then
  guard_fail stale-skips "Remove the skip named below and make the spec pass, or name the unfinished task it waits for in a comment above the skip." "$out"
else
  echo "Guard stale-skips: clean."
fi

# 8. Lint: ruff, prettier, eslint, gitleaks and the file checks (.pre-commit-config.yaml). The first
# pass may rewrite files (ruff format, prettier); the second must come back clean.
if ! command -v pre-commit >/dev/null 2>&1; then
  MISSING+=("pre-commit")
else
  if [ "$ALL" -eq 1 ]; then LINT_ARGS=(--all-files); else LINT_ARGS=(--files ${CHANGED[@]+"${CHANGED[@]}"}); fi
  if [ "$ALL" -eq 0 ] && [ "${#CHANGED[@]}" -eq 0 ]; then
    echo "Guard lint: no changed files."
  elif pre-commit run "${LINT_ARGS[@]}" >/tmp/sellos-guards-lint.$$ 2>&1 \
    || pre-commit run "${LINT_ARGS[@]}" >/tmp/sellos-guards-lint.$$ 2>&1; then
    echo "Guard lint: clean."
  else
    guard_fail lint "Fix each finding below in the code. ruff format and prettier have already rewritten what they can. Never add a noqa, an eslint-disable or an ignore to pass." "$(grep -v -E 'Passed$|Skipped$' /tmp/sellos-guards-lint.$$ | head -80)"
  fi
  rm -f /tmp/sellos-guards-lint.$$
fi

# 9. Semgrep with the Frappe rules, the rules CI uses. --all runs CI's exact command (semgrep ci,
# reading .semgrepignore); otherwise the changed files that .semgrepignore does not skip.
if [ ! -x "$SEMGREP" ] || [ ! -d "$SEMGREP_RULES" ]; then
  MISSING+=("Semgrep or the Frappe rules (run scripts/make-baseline.sh once)")
else
  SG_OUT=/tmp/sellos-guards-semgrep.$$
  if [ "$ALL" -eq 1 ]; then
    "$SEMGREP" ci --config "$SEMGREP_RULES" --config r/python.lang.correctness >"$SG_OUT" 2>"$SG_OUT.err"
    rc=$?
  else
    TARGETS=()
    for f in ${CHANGED[@]+"${CHANGED[@]}"}; do
      case "$f" in *.py | *.js | *.json | *.vue) ;; *) continue ;; esac
      git check-ignore -q --no-index "$f" 2>/dev/null && continue
      python3 - "$f" <<'PY' && TARGETS+=("$f")
import fnmatch, sys
from pathlib import Path
path = sys.argv[1]
for raw in Path(".semgrepignore").read_text().splitlines():
	pat = raw.strip()
	if not pat or pat.startswith("#"):
		continue
	if pat.endswith("/"):
		if path.startswith(pat) or f"/{pat}" in f"/{path}":
			sys.exit(1)
	elif fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(Path(path).name, pat):
		sys.exit(1)
PY
    done
    if [ "${#TARGETS[@]}" -eq 0 ]; then
      echo "Semgrep: no changed file to scan." >"$SG_OUT"
      rc=0
    else
      "$SEMGREP" scan --error --metrics=off --disable-version-check --config "$SEMGREP_RULES" \
        --config r/python.lang.correctness "${TARGETS[@]}" >"$SG_OUT" 2>"$SG_OUT.err"
      rc=$?
    fi
  fi
  if [ "$rc" -eq 0 ]; then
    echo "Guard semgrep: clean."
  else
    guard_fail semgrep "Rewrite the code each finding below names, the way the rule's message says (a list comprehension instead of map/filter, frappe.get_site_path or a checked path instead of a bare open(), and so on). Never add a nosemgrep comment to pass." "$(if grep -q 'Code Finding' "$SG_OUT"; then sed -n '/Code Finding/,$p' "$SG_OUT" | grep -v '^ *$' | head -80; else tail -15 "$SG_OUT.err"; fi)"
  fi
  rm -f "$SG_OUT" "$SG_OUT.err"
fi

ELAPSED=$(($(date +%s) - START))
if [ "${#MISSING[@]}" -gt 0 ]; then
  printf 'Guards could not run: %s is missing. This is the environment, not the code.\n' "${MISSING[*]}"
  exit 3
fi
if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "=== GUARDS FAILED in ${ELAPSED}s: ${FAILED[*]} (docs/GUARDS.md explains each) ==="
  exit 1
fi
echo "=== GUARDS PASSED in ${ELAPSED}s ==="
