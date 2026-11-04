#!/usr/bin/env python3
"""Fails when staged code changes arrive without a staged test change.

Set SELLOS_NO_TEST_REASON to waive it. The reason is written to .git/sellos_gate_waivers.
"""

import os
import re
import subprocess
import sys
import time

CODE = [re.compile(r"^sellos/.+\.py$"), re.compile(r"^frontend/src/.+\.(js|vue)$")]
EXEMPT = [
	re.compile(p)
	for p in (
		r"/__init__\.py$",
		r"^sellos/hooks\.py$",
		r"^sellos/patches/",
		r"^sellos/config/",
		r"^sellos/testing/",
		r"^frontend/src/theme/",
		r"^frontend/src/main\.js$",
	)
]
TESTS = [re.compile(p) for p in (r"(^|/)test_[^/]*\.py$", r"\.test\.js$")]


def staged_files():
	out = subprocess.run(
		["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
		capture_output=True,
		text=True,
		check=True,
	).stdout
	return [line for line in out.splitlines() if line]


def is_test(path):
	return any(p.search(path) for p in TESTS)


def needs_test(path):
	if is_test(path) or any(p.search(path) for p in EXEMPT):
		return False
	return any(p.search(path) for p in CODE)


def main():
	files = staged_files()
	code = [f for f in files if needs_test(f)]
	if not code or any(is_test(f) for f in files):
		return 0

	reason = os.environ.get("SELLOS_NO_TEST_REASON", "").strip()
	if reason:
		root = subprocess.run(
			["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
		).stdout.strip()
		# Fixed path under the repo's own .git folder, no user input (P0.07).
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		with open(os.path.join(root, ".git", "sellos_gate_waivers"), "a", encoding="utf-8") as f:
			f.write(f"{int(time.time())} no test: {reason}: {', '.join(code)}\n")
		print(f"Test requirement waived: {reason}")
		return 0

	print("These files changed but no test file did:")
	for f in code:
		print(f"  {f}")
	print("Add or update a test (test_*.py or *.test.js) in the same commit.")
	return 1


if __name__ == "__main__":
	sys.exit(main())
