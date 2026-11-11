#!/usr/bin/env python3
"""Reads a Cypress run log and the flaky log for scripts/lib/ui_flaky.sh (SOS-SETUP-27).

  ui_flaky.py failed-specs <cypress log>        one failing spec per line, in run order, each once
  ui_flaky.py too-flaky <flaky log> <limit>     "<spec> (<n> times)" for every spec logged <limit>+ times
  ui_flaky.py count <flaky log> <spec>          how many times <spec> is in the flaky log

Cypress colours its output when it thinks it has a terminal, and CI's log keeps the codes: in run
42925739766 the line was "\\x1b[90mFailing:\\x1b[39m      \\x1b[31m1\\x1b[39m". Stripping every non-digit
from that line, as the gate's old awk did, reads "903931139" failures and the spec name keeps its
colour codes. Every line is stripped of ANSI codes before it is read.

The flaky log has one line per rerun that passed: "<YYYY-MM-DD> <spec>".
"""

import re
import sys
from collections import Counter
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
FAILING = re.compile(r"\bFailing:\s+(\d+)")
SPEC_RAN = re.compile(r"\bSpec Ran:\s+(\S+)")


def read(path):
	p = Path(path)
	return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def failed_specs(text):
	"""The specs whose results box says Failing: 1 or more. The box gives Failing before Spec Ran."""
	out, failing = [], 0
	for raw in text.splitlines():
		line = ANSI.sub("", raw)
		m = FAILING.search(line)
		if m:
			failing = int(m.group(1))
			continue
		m = SPEC_RAN.search(line)
		if m:
			if failing > 0 and m.group(1) not in out:
				out.append(m.group(1))
			failing = 0
	return out


def flaky_counts(text):
	counts = Counter()
	for line in text.splitlines():
		parts = line.split()
		if len(parts) >= 2:
			counts[parts[1]] += 1
	return counts


def main(argv):
	if len(argv) == 2 and argv[0] == "failed-specs":
		print("\n".join(failed_specs(read(argv[1]))))
		return 0
	if len(argv) == 3 and argv[0] == "too-flaky":
		limit = int(argv[2])
		for spec, n in sorted(flaky_counts(read(argv[1])).items()):
			if n >= limit:
				print(f"{spec} ({n} times)")
		return 0
	if len(argv) == 3 and argv[0] == "count":
		print(flaky_counts(read(argv[1]))[argv[2]])
		return 0
	print(__doc__, file=sys.stderr)
	return 2


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
