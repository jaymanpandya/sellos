#!/usr/bin/env python3
"""Fails when a skipped Cypress spec outlives the task it waits for (SOS-SETUP-16).

Usage: check_no_stale_skips.py [--current <TASK_ID>] [TASKS_FILE] [SPEC_DIR]
Defaults: TASKS.md and cypress/integration, relative to the working directory.

The gate runs the whole Cypress suite, so a spec written as the contract of a later task is skipped
(context.skip, describe.skip or it.skip) until that task is worked. The skip names its task: the
task IDs on the skip line and in the comment lines directly above it. This check fails when:

* a skip names no task ID,
* a skip names a task whose status in TASKS_FILE is Complete, or that TASKS_FILE does not have,
* a skip names the task the gate is running for (--current), because that task is about to be
  marked Complete and must remove its skip first.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import tasks

SKIP = re.compile(r"\b(?:context|describe|it)\.skip\s*\(")
TASK_ID = re.compile(r"\bSOS-[A-Z0-9]+-[0-9]+[A-Z]?\b")
COMMENT = re.compile(r"^\s*(//|/\*|\*)")


def skips(path):
	"""(line number, task IDs) for every skip in a spec file."""
	lines = path.read_text(encoding="utf-8").splitlines()
	found = []
	for i, line in enumerate(lines):
		if not SKIP.search(line):
			continue
		ids = set(TASK_ID.findall(line))
		j = i - 1
		while j >= 0 and COMMENT.match(lines[j]):
			ids.update(TASK_ID.findall(lines[j]))
			j -= 1
		found.append((i + 1, sorted(ids)))
	return found


def problems(tasks_file, spec_dir, current=None):
	status = {t["id"]: t["status"] for t in tasks.parse(str(tasks_file))}
	out = []
	for path in sorted(Path(spec_dir).rglob("*.cy.js")):
		for line_no, ids in skips(path):
			where = f"{path}:{line_no}"
			if not ids:
				out.append(f"{where}: a skip names no task. Name the task that removes it in a comment.")
			for task_id in ids:
				if task_id == current:
					out.append(f"{where}: {task_id} is the task being finished. Remove its skip.")
				elif task_id not in status:
					out.append(f"{where}: {task_id} is not a task in {tasks_file}.")
				elif status[task_id] == "Complete":
					out.append(f"{where}: {task_id} is Complete, so this skip is stale. Remove it.")
	return out


def main(argv):
	current = None
	if argv[:1] == ["--current"]:
		if len(argv) < 2:
			print("Usage: check_no_stale_skips.py [--current <TASK_ID>] [TASKS_FILE] [SPEC_DIR]")
			return 2
		current, argv = argv[1], argv[2:]
	tasks_file = Path(argv[0]) if len(argv) > 0 else Path("TASKS.md")
	spec_dir = Path(argv[1]) if len(argv) > 1 else Path("cypress/integration")
	found = problems(tasks_file, spec_dir, current)
	if found:
		print("Stale skips: a skipped spec waits for a task that is done, or names none:")
		for line in found:
			print(f"  {line}")
		return 1
	print("Skipped specs: every skip waits for a task that is not Complete.")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
