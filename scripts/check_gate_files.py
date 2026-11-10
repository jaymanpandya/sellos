#!/usr/bin/env python3
"""Fails when a task edits the files that decide whether it passes.

Usage: check_gate_files.py <BASE_SHA> <TASK_BLOCK_FILE>
A task may change these files only when its block in TASKS.md says "- **Gate files:** allowed",
which only a human writes. The build loop passes the block in a file.

pyproject.toml is not protected as a whole, because tasks add dependencies to it. Its [tool.ruff]
tables decide what lint passes, so any change to them (rules, ignores, per file ignores, format)
fails the same way a protected file does.
"""

import fnmatch
import subprocess
import sys
import tomllib
from pathlib import Path

PROTECTED = [
	"scripts/run-tests.sh",
	"scripts/build-loop.sh",
	"scripts/watchdog.sh",
	"scripts/select-next-task.sh",
	"scripts/set-task-status.sh",
	"scripts/make-baseline.sh",
	"scripts/notify-telegram.sh",
	"scripts/lib/*",
	"scripts/check_*.py",
	# Named as well as matched, so narrowing the pattern above cannot unprotect it (SOS-SETUP-16).
	"scripts/check_no_stale_skips.py",
	"scripts/check_ci_parity.py",
	"scripts/check_site_set.py",
	"scripts/check_no_secret_leak.py",
	"scripts/lib/db_secrets.sh",
	"cypress.config.js",
	"cypress/support/e2e.js",
	".pre-commit-config.yaml",
	".semgrepignore",
	".eslintrc",
	".github/workflows/*",
	"docs/DEV_STRATEGY.md",
	"docs/TESTING.md",
	"scripts/prepare-regression.sh",
	"docs/regression/README.md",
	# The regression pause switches (SOS-SETUP-19).
	"scripts/pause-loop.sh",
	"scripts/resume-loop.sh",
	# The BuildOS reference copy and the shared bench helpers (SOS-SETUP-21).
	"scripts/refresh-buildos-reference.sh",
	"scripts/install-shared-helpers.sh",
	"scripts/shared/*",
]

# A task adds its flows here, so the file is not protected from a change. A flow already in it may
# not be removed or edited, which is the same ratchet check_assertion_ratchet.py applies to tests.
FLOWS_FILE = "docs/regression/flows.md"

PYPROJECT = "pyproject.toml"


def changed(base):
	out = subprocess.run(
		["git", "status", "--porcelain", "-uall"], capture_output=True, text=True, check=True
	).stdout
	files = set()
	for line in out.splitlines():
		path = line[3:].split(" -> ")[-1]
		files.add(path)
	diff = subprocess.run(
		["git", "diff", "--name-only", base], capture_output=True, text=True, check=True
	).stdout
	files.update(p for p in diff.splitlines() if p)
	return sorted(files)


def removed_flows(base):
	"""FLOW lines the working tree no longer has compared with the base commit."""
	out = subprocess.run(
		["git", "diff", base, "--", FLOWS_FILE], capture_output=True, text=True, check=True
	).stdout
	return [line[1:] for line in out.splitlines() if line.startswith("-FLOW")]


def ruff_tables(text):
	"""The [tool.ruff] tables of a pyproject.toml, or None when the file has none."""
	return tomllib.loads(text).get("tool", {}).get("ruff")


def ruff_changed(base):
	"""True when [tool.ruff] in the working tree differs from the base commit in any way."""
	shown = subprocess.run(["git", "show", f"{base}:{PYPROJECT}"], capture_output=True, text=True)
	before = shown.stdout if shown.returncode == 0 else ""
	path = Path(PYPROJECT)
	after = path.read_text(encoding="utf-8") if path.exists() else ""
	try:
		return ruff_tables(before) != ruff_tables(after)
	except tomllib.TOMLDecodeError as e:
		print(f"{PYPROJECT} does not parse, so its [tool.ruff] tables cannot be checked: {e}")
		return True


def main():
	base, block_file = sys.argv[1], sys.argv[2]
	# A path the build loop passes in, not user input.
	with open(block_file, encoding="utf-8") as f:  # nosemgrep
		block = f.read()
	if "**Gate files:** allowed" in block:
		print("Gate files: this task is allowed to change them.")
		return 0

	lost = removed_flows(base)
	if lost:
		print(
			f"Gate files FAILED. {FLOWS_FILE} lost or changed flows. A task may add flows, never remove one:"
		)
		for line in lost:
			print(f"  {line}")
		return 1

	hits = [p for p in changed(base) if any(fnmatch.fnmatch(p, pat) for pat in PROTECTED)]
	if ruff_changed(base):
		hits.append(f"{PYPROJECT} [tool.ruff] (a dependency change is allowed, a lint setting change is not)")
	if not hits:
		print("Gate files: untouched.")
		return 0
	print("Gate files FAILED. A task may not change the files that judge it:")
	for p in hits:
		print(f"  {p}")
	print('Only a human may allow this, by adding "- **Gate files:** allowed" to the task.')
	return 1


if __name__ == "__main__":
	sys.exit(main())
