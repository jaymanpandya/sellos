#!/usr/bin/env bash
# ci-rehearsal.sh: run CI's steps on a fresh clone of the last commit, before a push (SOS-SETUP-33).
#
#   scripts/ci-rehearsal.sh [ref]       default HEAD; works from any directory
#
# CI sees only what is committed. A fresh clone shows what CI will see: a file that exists here but is
# untracked, ignored or built locally is missing there, as it was for the built web page (bench get-app
# clones tracked files only). The rehearsal runs, in a clone under a temporary folder:
#
#   Linters job   scripts/check-guards.sh --all (pre-commit, semgrep ci and the code guards), and
#                 pip-audit when it is installed
#   Frontend job  scripts/build-web-app.sh (npm ci, npm run build)
#   Server, UI    every script the workflows call exists in the clone, is tracked, and parses
#                 (bash -n, python3 -m py_compile); the local bench matches ci.yml
#                 (scripts/check_ci_parity.py). Their test runs need a fresh bench and a MariaDB
#                 root login, which the shared bench must never give (CLAUDE.md, Shared bench), so
#                 they are not run here; docs/CI_DIFFERENCES.md lists that difference.
#
# Nothing in this repository, the bench or any site is changed. Exit 0 when every step passes, 1 when
# one fails, and the summary names each step.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
REF="${1:-HEAD}"
SHA="$(git -C "$REPO_DIR" rev-parse --verify "$REF^{commit}")" || { echo "No commit '$REF'." >&2; exit 2; }
WORK="$(mktemp -d "${TMPDIR:-/tmp}/sellos-ci-rehearsal.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
CLONE="$WORK/sellos"
RESULTS=()
FAILED=0

step() { # name, then the command
  local name="$1" start rc
  shift
  echo
  echo "=== $name ==="
  start="$(date +%s)"
  "$@"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    RESULTS+=("PASS  $name ($(($(date +%s) - start)) s)")
  else
    RESULTS+=("FAIL  $name (exit $rc)")
    FAILED=1
  fi
}

if [ -n "$(git -C "$REPO_DIR" status --porcelain)" ]; then
  echo "Note: the working tree has uncommitted changes. CI never sees them, and neither does this rehearsal."
fi
echo "Cloning ${SHA:0:9} into $CLONE"
git clone --quiet --no-hardlinks "$REPO_DIR" "$CLONE" && git -C "$CLONE" checkout --quiet "$SHA" || exit 1

workflow_scripts() {
  grep -h -o -E 'scripts/[A-Za-z0-9_./-]+\.(sh|py)' "$CLONE"/.github/workflows/*.yml | sort -u
}

scripts_exist_and_parse() {
  local f bad=0
  while IFS= read -r f; do
    if ! git -C "$CLONE" ls-files --error-unmatch "$f" >/dev/null 2>&1; then
      echo "MISSING in the commit: $f (a workflow calls it, and CI gets only tracked files)"
      bad=1
      continue
    fi
    case "$f" in
      *.sh) bash -n "$CLONE/$f" || { echo "Does not parse: $f"; bad=1; } ;;
      *.py) python3 -m py_compile "$CLONE/$f" || { echo "Does not compile: $f"; bad=1; } ;;
    esac
    echo "ok  $f"
  done < <(workflow_scripts)
  return "$bad"
}

linters() {
  (cd "$CLONE" && bash scripts/check-guards.sh --all) || return 1
  if command -v pip-audit >/dev/null 2>&1; then
    (cd "$CLONE" && pip-audit --desc on .)
  else
    echo "pip-audit is not installed here, so the Vulnerable Dependency Check job is not rehearsed."
  fi
}

step "Server and UI: every script the workflows call is in the commit and parses" scripts_exist_and_parse
step "Server and UI: the local bench matches ci.yml (Frappe branch, Python, Node)" \
  python3 "$CLONE/scripts/check_ci_parity.py" "$BENCH_DIR" "$CLONE/.github/workflows/ci.yml"
step "Linters: scripts/check-guards.sh --all" linters
step "Frontend: scripts/build-web-app.sh" bash "$CLONE/scripts/build-web-app.sh"

echo
echo "=== CI rehearsal of ${SHA:0:9} ==="
printf '%s\n' "${RESULTS[@]}"
echo "Not rehearsed: the Server and UI test runs (a fresh bench and MariaDB root, see docs/CI_DIFFERENCES.md)."
exit "$FAILED"
