#!/usr/bin/env python3
"""Fails when a task edits the files that decide whether it passes.

Usage: check_gate_files.py <BASE_SHA> <TASK_BLOCK_FILE>
A task may change these files only when its block in TASKS.md says "- **Gate files:** allowed",
which only a human writes. The build loop passes the block in a file.
"""

import fnmatch
import subprocess
import sys

PROTECTED = [
	"scripts/run-tests.sh",
	"scripts/build-loop.sh",
	"scripts/watchdog.sh",
	"scripts/select-next-task.sh",
	"scripts/set-task-status.sh",
	"scripts/make-baseline.sh",
	"scripts/lib/*",
	"scripts/check_*.py",
	"cypress.config.js",
	"cypress/support/e2e.js",
	".pre-commit-config.yaml",
	".github/workflows/*",
	"docs/DEV_STRATEGY.md",
	"docs/TESTING.md",
	"scripts/prepare-regression.sh",
	"docs/regression/README.md",
]

# A task adds its flows here, so the file is not protected from a change. A flow already in it may
# not be removed or edited, which is the same ratchet check_assertion_ratchet.py applies to tests.
FLOWS_FILE = "docs/regression/flows.md"


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
