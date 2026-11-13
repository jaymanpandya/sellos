#!/usr/bin/env python3
"""The repeat plan of the flake check (SOS-SETUP-34).

Every new or changed test runs more than once in the gate, and a failure on any run fails it
(SOS-SETUP-33). The number of runs shrinks as a test gets slower, measured by its first run:

  first run under 60 seconds     5 runs
  first run under 3 minutes      3 runs
  first run of 3 minutes or more 2 runs

and the repeats (every run after the first) of one gate together get at most 10 minutes
(SELLOS_FLAKE_CAP_SECONDS, 600). When the planned repeats do not fit, they are shared out one round at
a time, in the order the targets ran, so every test gets its first repeat before any gets its second.
SELLOS_FLAKE_RUNS, when set, lowers the number of runs of every tier to at most that many.

  flake_plan.py plan <durations file> <plan file>

The durations file has one line per target, "kind<TAB>target<TAB>seconds of its first run". The plan
file gets one line per target, "runs" (the first run included), in the same order. The plan a person
reads is printed.
"""

import os
import sys
from pathlib import Path

TIERS = ((60, 5), (180, 3))
SLOWEST_RUNS = 2
DEFAULT_CAP_SECONDS = 600


def runs_for(seconds, most=None):
	"""Runs for a test whose first run took this many seconds, the first run included."""
	runs = SLOWEST_RUNS
	for limit, tier_runs in TIERS:
		if seconds < limit:
			runs = tier_runs
			break
	return min(runs, most) if most else runs


def plan(durations, cap_seconds=DEFAULT_CAP_SECONDS, most=None):
	"""For [(target, seconds)], the runs each gets ([int]) with the repeats inside the cap."""
	wanted = [runs_for(seconds, most) - 1 for _, seconds in durations]
	granted = [0] * len(durations)
	spent = 0
	progress = True
	while progress:
		progress = False
		for i, (_, seconds) in enumerate(durations):
			if granted[i] < wanted[i] and spent + seconds <= cap_seconds:
				granted[i] += 1
				spent += seconds
				progress = True
	return [1 + g for g in granted], [1 + w for w in wanted], spent


def describe(durations, runs, wanted, spent, cap_seconds):
	lines = [
		f"=== Repeat plan: {len(durations)} changed test(s); runs by first run time: under 60s 5, "
		f"under 3 min 3, otherwise 2; repeats capped at {cap_seconds}s per gate ==="
	]
	for (target, seconds), got, want in zip(durations, runs, wanted, strict=True):
		note = ""
		if got < want:
			note = f" (wanted {want}, cut to fit the {cap_seconds}s cap)"
		lines.append(
			f"  {target}: first run {seconds}s, {got} run(s) in all, {(got - 1) * seconds}s more{note}"
		)
	lines.append(f"  Planned repeat time: {spent}s of {cap_seconds}s.")
	return "\n".join(lines)


def main(argv):
	if len(argv) != 3 or argv[0] != "plan":
		print(__doc__, file=sys.stderr)
		return 2
	cap = int(os.environ.get("SELLOS_FLAKE_CAP_SECONDS") or DEFAULT_CAP_SECONDS)
	most_text = os.environ.get("SELLOS_FLAKE_RUNS") or ""
	if most_text and not (most_text.isdigit() and int(most_text) > 0):
		print(f"SELLOS_FLAKE_RUNS must be a whole number of runs, not '{most_text}'.", file=sys.stderr)
		return 1
	most = int(most_text) if most_text else None
	durations = []
	for line in Path(argv[1]).read_text(encoding="utf-8").splitlines():
		if line.strip():
			_kind, target, seconds = line.split("\t")
			durations.append((target, int(seconds)))
	runs, wanted, spent = plan(durations, cap, most)
	Path(argv[2]).write_text("".join(f"{r}\n" for r in runs), encoding="utf-8")
	print(describe(durations, runs, wanted, spent, cap))
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
