#!/usr/bin/env python3
"""SOS-SETUP-38: read the failed jobs' logs of a red CI run (gh run view <id> --log-failed).

Usage:
  ci_failures.py extract <log>   the failing tests and their messages, one per line, at most 80 lines
  ci_failures.py kind <log>      "code", "environment <the line that shows it>" or "flake-counter"
  ci_failures.py flaky <log>     the specs the flake counter names, one per line

A red run is the environment's only when its log names no failing test and shows a runner, quota or
network fault (a runner lost or shut down, a job GitHub would not start, a host that does not
resolve, a rate limit, a 5xx from a service). Any failing test makes it the code's, whatever else the
log says, so a repair agent sees it. The build loop reruns an environmental failure once before it
stops, and repairs a code failure (scripts/build-loop.sh, ci_until_green).
"""

import re
import sys

ANSI = re.compile(r"\x1b\[[0-9;]*m|\^\[\[[0-9;]*m")
# gh --log-failed lines: "<job>\t<step>\t<timestamp> <text>".
PREFIX = re.compile(r"^[^\t]*\t[^\t]*\t(?:﻿)?\d{4}-\d\d-\d\dT[\d:.]+Z ?")
STAMP = re.compile(r"^(?:﻿)?\d{4}-\d\d-\d\dT[\d:.]+Z ?")

FAILURE = re.compile(
	r"^\s*(FAIL|ERROR):? "  # a unittest failure header
	r"|^\s*[A-Za-z_][\w.]*(Error|Exception|Failure)(:|$)"  # its message
	r"|^\s*\d+\) "  # a numbered Cypress failure (title, and its hook)
	r"|^\s*-\[ '"  # an unexpected console error list, as cypress/support/e2e.js prints it
	r"|FLAKY too often|SPEC FAILED|SPECS FAILED|TESTS FAILED|GUARD FAILED|GUARDS FAILED"
	r"|^\s*FLAKY \(passed on rerun\)"
)
NOT_A_FAILURE = re.compile(r"✔|✓|^\s*FAILED \(|Error: Process completed with exit code")

ENVIRONMENT = re.compile(
	r"The runner has received a shutdown signal"
	r"|lost communication with the server"
	r"|The hosted runner .*(lost|encountered an error)"
	r"|The job was not started"
	r"|spending limit|recent account payments have failed|billing"
	r"|Could not resolve host|Temporary failure in name resolution|Name or service not known"
	r"|Failed to connect to (github\.com|api\.github\.com|pypi\.org|registry\.npmjs\.org)"
	r"|fatal: unable to access 'https://"
	r"|API rate limit exceeded|secondary rate limit"
	r"|(502 Bad Gateway|503 Service Unavailable|504 Gateway Time-?out)"
	r"|No space left on device",
	re.I,
)


def clean(line):
	line = ANSI.sub("", line.rstrip("\n"))
	line = PREFIX.sub("", line, count=1)
	return STAMP.sub("", line, count=1)


def lines_of(path):
	with open(path, encoding="utf-8", errors="replace") as f:  # nosemgrep: a log path the loop passes
		return [clean(line) for line in f]


def extract(lines):
	seen, out = set(), []
	for line in lines:
		if not FAILURE.search(line) or NOT_A_FAILURE.search(line):
			continue
		text = line.strip()[:300]
		if text and text not in seen:
			seen.add(text)
			out.append(text)
	return out[:80]


# A run that is red only because of the flake counter: the suite printed "FLAKY too often" and nothing
# else failed. A numbered Cypress failure is not counted, because a spec that failed once and passed on
# its rerun still prints it; a spec that failed its rerun prints FAILED AGAIN.
HARD_FAILURE = re.compile(
	r"^\s*(FAIL|ERROR):? "
	r"|FAILED AGAIN|UI tests failed|SPEC FAILED|SPECS FAILED|TESTS FAILED|GUARD FAILED|GUARDS FAILED"
	r"|^\s*FAILED \((failures|errors)="
)
TOO_OFTEN = re.compile(r"FLAKY too often, fix these specs:\s*(.*?)\s*-*\s*$")
RERUN_PASSED = re.compile(r"^\s*FLAKY \(passed on rerun\):\s*(\S+)")


def flake_counter_only(lines):
	if not any(TOO_OFTEN.search(line) for line in lines):
		return False
	return not any(HARD_FAILURE.search(line) for line in lines)


def flaky_specs(lines):
	specs = []
	for line in lines:
		m = TOO_OFTEN.search(line)
		found = m.group(1).split() if m else []
		m = RERUN_PASSED.search(line)
		if m:
			found = [m.group(1)]
		for spec in found:
			if spec not in specs:
				specs.append(spec)
	return specs


def kind(lines):
	if flake_counter_only(lines):
		return "flake-counter"
	if extract(lines):
		return "code"
	for line in lines:
		if ENVIRONMENT.search(line):
			return "environment " + line.strip()[:200]
	return "code"


def main(argv):
	if len(argv) != 2 or argv[0] not in ("extract", "kind", "flaky"):
		print(__doc__)
		return 2
	lines = lines_of(argv[1])
	if argv[0] == "extract":
		print("\n".join(extract(lines)))
	elif argv[0] == "flaky":
		print("\n".join(flaky_specs(lines)))
	else:
		print(kind(lines))
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
