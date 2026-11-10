#!/usr/bin/env python3
"""Read a backend test log for database conflicts, and name the modules that failed (SOS-SETUP-25).

Usage:
  db_conflict.py is-conflict <log>       exit 0 when the log holds a MariaDB 1020 or deadlock error
  db_conflict.py failing-modules <log>   print each failing test module once, one per line

A MariaDB 1020 ("Record has changed since last read") or a deadlock (1213) in a test is a timing race
with another connection, usually the shared bench worker, not a fault in the code. On 10 November
2026 one Blocked SOS-P1-06A and used up its repair runs. scripts/run-tests.sh reruns only the
failing modules once when the log holds one, and exits 3 (an environment problem) if the rerun hits
one again.
"""

import re
import sys
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
CONFLICT = re.compile(
	r"QueryDeadlockError"
	r"|\(1020, ['\"]Record has changed since last read"
	r"|\(1213, ['\"]Deadlock found when trying to get lock"
)
# unittest's failure header, as Frappe's runner prints it: " ERROR  test_x (pkg.mod.Class.test_x)",
# and the plain form "ERROR: test_x (pkg.mod.Class.test_x)". setUpClass names only the class.
FAILURE = re.compile(r"^\s*(?:ERROR|FAIL):?\s+\S+\s+\(([A-Za-z_][\w.]*)\)\s*$")


def plain(path):
	return ANSI.sub("", Path(path).read_text(encoding="utf-8", errors="replace"))


def is_conflict(text):
	return bool(CONFLICT.search(text))


def module_of(dotted):
	"""pkg.mod.Class.test_x -> pkg.mod. The module is every part before the first class name."""
	parts = dotted.split(".")
	for i, part in enumerate(parts):
		if part[:1].isupper():
			return ".".join(parts[:i]) or None
	return None


def failing_modules(text):
	seen = []
	for line in text.splitlines():
		match = FAILURE.match(line)
		if match:
			module = module_of(match.group(1))
			if module and module not in seen:
				seen.append(module)
	return seen


def main(argv):
	if len(argv) != 3 or argv[1] not in ("is-conflict", "failing-modules"):
		print("usage: db_conflict.py is-conflict|failing-modules <log>", file=sys.stderr)
		return 2
	text = plain(argv[2])
	if argv[1] == "is-conflict":
		return 0 if is_conflict(text) else 1
	for module in failing_modules(text):
		print(module)
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv))
