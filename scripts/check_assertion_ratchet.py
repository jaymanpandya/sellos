#!/usr/bin/env python3
"""Fails when a task weakens the tests: a test file deleted, or fewer assertions than before.

Usage: check_assertion_ratchet.py <BASE_SHA>
Compares every test file (test_*.py and *.cy.js) in the working tree with the same file at
BASE_SHA. A human can allow a drop for one run with SELLOS_ALLOW_ASSERTION_DROP="reason". The
build loop never sets it. Cypress and Frappe tests are counted by their assertion calls.
"""

import os
import re
import subprocess
import sys

PY_ASSERT = re.compile(r"\bself\.assert\w+\(|^\s*assert\s|\bwith\s+self\.assertRaises\b", re.M)
JS_ASSERT = re.compile(r"\.should\(|\.and\(|\bexpect\(|\.its\([^)]*\)\.should")
TEST_FILE = re.compile(r"(^|/)test_[^/]*\.py$|\.cy\.js$")


def git(*args, check=True):
	return subprocess.run(["git", *args], capture_output=True, text=True, check=check).stdout


def count(path, text):
	pattern = JS_ASSERT if path.endswith(".js") else PY_ASSERT
	return len(pattern.findall(text))


def main():
	base = sys.argv[1]
	files = set()
	for line in git("diff", "--name-status", base).splitlines():
		parts = line.split("\t")
		files.update(p for p in parts[1:] if TEST_FILE.search(p))
	for line in git("ls-files", "--others", "--exclude-standard").splitlines():
		if TEST_FILE.search(line):
			files.add(line)

	problems = []
	for path in sorted(files):
		old = git("show", f"{base}:{path}", check=False)
		if not old:
			continue  # a new file cannot be weaker than nothing
		if not os.path.exists(path):
			problems.append(f"{path}: deleted ({count(path, old)} assertions)")
			continue
		# A path the build loop passes in, not user input.
		with open(path, encoding="utf-8") as f:  # nosemgrep
			new = f.read()
		before, after = count(path, old), count(path, new)
		if after < before:
			problems.append(f"{path}: assertions dropped from {before} to {after}")

	if not problems:
		print("Assertion ratchet: no test was weakened.")
		return 0

	reason = os.environ.get("SELLOS_ALLOW_ASSERTION_DROP", "").strip()
	if reason:
		print(f"Assertion ratchet waived by a human: {reason}")
		for p in problems:
			print(f"  {p}")
		return 0

	print("Assertion ratchet FAILED. A task may add tests but never remove or weaken them:")
	for p in problems:
		print(f"  {p}")
	return 1


if __name__ == "__main__":
	sys.exit(main())
