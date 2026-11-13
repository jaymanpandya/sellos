#!/usr/bin/env python3
"""The stop ledger, docs/STOPS.md (SOS-SETUP-33).

Every time the build loop stops, it appends one row: the time, the task, a category, the cause, the
minutes the attempt took and produced nothing, and, filled in when the loop next starts, the hours
it stood idle until someone restarted it. The loop prints the hours since the last stop and the
number of tasks finished since then. The exit test (docs/DEV_STRATEGY.md section 11) is ten tasks
in a row without an unplanned stop.

  stops.py record <file> <task> <category> <cause> <attempt minutes>
  stops.py restarted <file>             fill the idle time of the last row, if it is empty
  stops.py since <file>                 hours since the last stop, one decimal ("never" with none)
  stops.py streak <file> <repo>         tasks the loop finished since the last unplanned stop
  stops.py summary <file> <repo>        one line for the loop and sellos status

Planned stops (a regression pause, a stop Jayman asked for) are recorded but do not end a streak.
"""

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HEADER = """# Stops

Every stop of the SellOS build loop, appended by `scripts/build-loop.sh` (SOS-SETUP-33). The loop
prints the hours since the last stop. The exit test in `docs/DEV_STRATEGY.md` section 11 is ten
consecutive tasks without an unplanned stop. Categories: `blocked` (the gate failed after its
repairs), `needs-input`, `crash`, `unrecognized`, `environment`, `ci-red`, `push-failed`,
`blocked-exists`, `no-work`, `start` (a check before any task), `unexpected`, and the planned ones,
`paused` and `stopped`. "Attempt lost" is the time from the task's start to the stop. "Idle until
restart" is filled in when the loop starts again.

| Time (UTC) | Task | Category | Cause | Attempt lost (min) | Idle until restart (h) |
| --- | --- | --- | --- | --- | --- |
"""
PLANNED = {"paused", "stopped"}
ROW = re.compile(
	r"^\| (\d{4}-\d\d-\d\d \d\d:\d\d) \| ([^|]*) \| ([^|]*) \| ([^|]*) \| ([^|]*) \| ([^|]*) \|$"
)
TIME_FORMAT = "%Y-%m-%d %H:%M"
# Commits the loop makes for a finished task are "<ID>: <title>". These subjects are not finished tasks.
NOT_A_TASK = re.compile(
	r"mark In Progress|salvage|marking Blocked|reset to Not Started|^SOS-SETUP-|^SOS-REG-|^SOS-LOOP:"
)
TASK_COMMIT = re.compile(r"^SOS-[A-Za-z0-9_-]+: ")


def now():
	return datetime.now(UTC)


def rows(path):
	try:
		text = Path(path).read_text(encoding="utf-8")
	except FileNotFoundError:
		return []
	found = []
	for line in text.splitlines():
		match = ROW.match(line.strip())
		if match:
			found.append([part.strip() for part in match.groups()])
	return found


def clean(text, limit=200):
	text = " ".join(str(text).split()).replace("|", "/")
	return text[: limit - 1] + "…" if len(text) > limit else text


def record(path, task, category, cause, minutes):
	path = Path(path)
	path.parent.mkdir(parents=True, exist_ok=True)
	if not path.exists() or "| Time (UTC) |" not in path.read_text(encoding="utf-8"):
		path.write_text(HEADER, encoding="utf-8")
	try:
		lost = f"{max(0, float(minutes)):.0f}"
	except ValueError:
		lost = "0"
	line = f"| {now().strftime(TIME_FORMAT)} | {clean(task or '-', 40)} | {clean(category, 20)} | {clean(cause)} | {lost} |  |\n"
	with path.open("a", encoding="utf-8") as handle:
		handle.write(line)


def parse_time(value):
	return datetime.strptime(value, TIME_FORMAT).replace(tzinfo=UTC)


def restarted(path):
	path = Path(path)
	if not path.exists():
		return
	lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
	for index in range(len(lines) - 1, -1, -1):
		match = ROW.match(lines[index].strip())
		if not match:
			continue
		parts = [part.strip() for part in match.groups()]
		if parts[5]:
			return
		idle = (now() - parse_time(parts[0])).total_seconds() / 3600
		parts[5] = f"{idle:.1f}"
		lines[index] = "| " + " | ".join(parts) + " |\n"
		path.write_text("".join(lines), encoding="utf-8")
		return


def since(path):
	found = rows(path)
	if not found:
		return "never"
	return f"{(now() - parse_time(found[-1][0])).total_seconds() / 3600:.1f}"


def last_unplanned(path):
	for parts in reversed(rows(path)):
		if parts[2] not in PLANNED:
			return parse_time(parts[0])
	return None


def streak(path, repo):
	after = last_unplanned(path)
	args = ["git", "-C", str(repo), "log", "--first-parent", "--format=%s"]
	if after:
		args.append(f"--since={after.strftime('%Y-%m-%dT%H:%M:%SZ')}")
	out = subprocess.run(args, capture_output=True, text=True, check=False).stdout
	return sum(1 for s in out.splitlines() if TASK_COMMIT.match(s) and not NOT_A_TASK.search(s))


def summary(path, repo):
	count = streak(path, repo)
	verdict = "the exit test is met" if count >= 10 else f"{10 - count} more for the exit test"
	return f"{since(path)} hours since the last stop; {count} task(s) finished since the last unplanned stop ({verdict})"


def main(argv):
	if len(argv) < 2:
		print(__doc__)
		return 2
	command, path = argv[0], argv[1]
	if command == "record" and len(argv) == 6:
		record(path, *argv[2:6])
	elif command == "restarted":
		restarted(path)
	elif command == "since":
		print(since(path))
	elif command == "streak" and len(argv) == 3:
		print(streak(path, argv[2]))
	elif command == "summary" and len(argv) == 3:
		print(summary(path, argv[2]))
	else:
		print(__doc__)
		return 2
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
