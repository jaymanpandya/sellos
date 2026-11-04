#!/usr/bin/env python3
"""Fails when a finished task has no test that names it.

Usage: check_task_evidence.py <TASK_ID> <BASE_SHA> <TASK_BLOCK_FILE>
A task needs at least one new or changed test file (test_*.py or *.cy.js) that mentions its ID,
and that file must hold assertions. A block with "- **Docs only:** yes" is exempt. A task whose
block says "- **Browser spec:** required" also needs a changed *.cy.js that names the task.
"""

import re
import subprocess
import sys

TEST_FILE = re.compile(r"(^|/)test_[^/]*\.py$|\.cy\.js$")
ASSERTION = re.compile(r"\bself\.assert\w+\(|^\s*assert\s|\.should\(|\bexpect\(", re.M)


def changed_files(base):
	files = set()
	out = subprocess.run(
		["git", "status", "--porcelain", "-uall"], capture_output=True, text=True, check=True
	).stdout
	for line in out.splitlines():
		if line[:2].strip() == "D":
			continue
		files.add(line[3:].split(" -> ")[-1])
	diff = subprocess.run(
		["git", "diff", "--name-only", "--diff-filter=AM", base],
		capture_output=True,
		text=True,
		check=True,
	).stdout
	files.update(p for p in diff.splitlines() if p)
	return sorted(f for f in files if TEST_FILE.search(f))


def main():
	task_id, base, block_file = sys.argv[1], sys.argv[2], sys.argv[3]
	# A path the build loop passes in, not user input.
	with open(block_file, encoding="utf-8") as f:  # nosemgrep
		block = f.read()
	if re.search(r"\*\*Docs only:\*\*\s*yes", block, re.I):
		print("Task evidence: docs only task, no test needed.")
		return 0

	named = []
	for path in changed_files(base):
		try:
			# A path the build loop passes in, not user input.
			with open(path, encoding="utf-8") as f:  # nosemgrep
				text = f.read()
		except OSError:
			continue
		if task_id in text and ASSERTION.search(text):
			named.append(path)

	if not named:
		print(f"Task evidence FAILED: no new or changed test names {task_id} and holds assertions.")
		print(f'Put "{task_id}" in the test class docstring or the Cypress context() title.')
		return 1

	if re.search(r"\*\*Browser spec:\*\*\s*required", block, re.I) and not any(
		p.endswith(".cy.js") for p in named
	):
		print(f"Task evidence FAILED: {task_id} needs a Cypress spec that names it.")
		return 1

	print(f"Task evidence: {task_id} is covered by {', '.join(named)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
