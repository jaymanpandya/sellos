#!/usr/bin/env python3
"""Shared TASKS.md parsing and mutation helpers for the SellOS build loop.

Zero LLM calls. Deterministic. Mirrors the JarvisCodes/OTT task selection
logic documented for that build:

  1. If any task is already "In Progress", resume that one first.
  2. Otherwise pick the first "Not Started" task, in file order, among the
     highest priority tier (P0 before P1 ... before P6), whose Dependencies
     are all "Complete".
  3. If nothing is eligible, report NONE_ELIGIBLE.

Implemented in Python rather than raw awk (unlike the original droplet
based scripts) for portability: macOS ships BSD awk, not GNU awk, and
multi line block parsing with a custom record separator is a GNU
extension that doesn't behave the same way on BSD awk. This keeps the
logic itself identical, just more portable for a local Mac run.

Known gap carried over deliberately, per the OTT build's own notes: this
does NOT auto resume a "Blocked" task. Reset it to "Not Started" by hand
once you've actually fixed the underlying problem, then relaunch the loop.
"""

import re
import sys

HEADER_RE = re.compile(r"^### (?P<id>[A-Za-z0-9_-]+):")
STATUS_RE = re.compile(r"^(?P<prefix>-\s*\*\*Status:\*\*\s*)(?P<value>.*)$")
PRIORITY_RE = re.compile(r"^-\s*\*\*Priority:\*\*\s*(?P<value>.*)$")
DEPS_RE = re.compile(r"^-\s*\*\*Dependencies:\*\*\s*(?P<value>.*)$")
OWNER_RE = re.compile(r"^-\s*\*\*Owner:\*\*\s*(?P<value>.*)$")

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6}


def parse(path):
	with open(path, "r", encoding="utf-8") as f:
		lines = f.readlines()

	tasks = []
	current = None
	for line in lines:
		m = HEADER_RE.match(line)
		if m:
			if current:
				tasks.append(current)
			current = {"id": m.group("id"), "status": "", "priority": "", "owner": "", "deps": []}
			continue
		if current is None:
			continue
		m = STATUS_RE.match(line.strip())
		if m:
			current["status"] = m.group("value").strip()
			continue
		m = PRIORITY_RE.match(line.strip())
		if m:
			current["priority"] = m.group("value").strip()
			continue
		m = OWNER_RE.match(line.strip())
		if m:
			current["owner"] = m.group("value").strip()
			continue
		m = DEPS_RE.match(line.strip())
		if m:
			raw = m.group("value").strip()
			if raw and raw.lower() != "none":
				current["deps"] = [d.strip() for d in raw.split(",") if d.strip()]
			continue
	if current:
		tasks.append(current)
	return tasks


def select_next(tasks):
	for t in tasks:
		if t["status"] == "In Progress":
			return t["id"]

	# Never pick new "Not Started" work while anything sits Blocked. A blocker
	# means the codebase is in a known-bad state; development halts entirely
	# until every Blocked task is actually root-caused and reset by hand.
	blocked = [t["id"] for t in tasks if t["status"] == "Blocked"]
	if blocked:
		return "BLOCKED_EXISTS:" + ",".join(blocked)

	complete_ids = {t["id"] for t in tasks if t["status"] == "Complete"}

	best = None
	best_rank = None
	for t in tasks:
		if t["status"] != "Not Started":
			continue
		if not all(d in complete_ids for d in t["deps"]):
			continue
		rank = PRIORITY_RANK.get(t["priority"], 9)
		if best is None or rank < best_rank:
			best = t
			best_rank = rank
	return best["id"] if best else "NONE_ELIGIBLE"


def waiting_report(tasks):
	"""Lines for the Waiting tasks that still hold up a Not Started task, and what each waits on.

	A Waiting task belongs to a person (or to Claude in chat for a regression milestone). The loop
	never picks it, so when nothing else is eligible this tells the person which ones to finish by
	hand: scripts/set-task-status.sh <ID> Complete TASKS.md, then commit and push.
	"""
	by_id = {t["id"]: t for t in tasks}
	lines = []
	for t in tasks:
		if t["status"] != "Waiting":
			continue
		held = [d["id"] for d in tasks if d["status"] == "Not Started" and t["id"] in d["deps"]]
		if not held:
			continue
		unmet = [
			f"{d} ({by_id[d]['status']})" if d in by_id else d
			for d in t["deps"]
			if d not in by_id or by_id[d]["status"] != "Complete"
		]
		if len(unmet) > 3:
			unmet = [*unmet[:3], f"{len(unmet) - 3} more"]
		waits = ", ".join(unmet) if unmet else f"its owner, {t['owner'] or 'unknown'}"
		lines.append(
			f"{t['id']} waits on {waits}; holds up {', '.join(held[:4])}{' and more' if len(held) > 4 else ''}"
		)
	return lines


def set_status(path, task_id, new_status):
	with open(path, "r", encoding="utf-8") as f:
		lines = f.readlines()

	in_target = False
	found_task = False
	changed = False
	out = []
	for line in lines:
		m = HEADER_RE.match(line)
		if m:
			in_target = m.group("id") == task_id
			if in_target:
				found_task = True
		if in_target:
			m = STATUS_RE.match(line.rstrip("\n"))
			if m:
				out.append(f"{m.group('prefix')}{new_status}\n")
				changed = True
				continue
		out.append(line)

	if not found_task:
		print(f"ERROR: task {task_id} not found in {path}", file=sys.stderr)
		sys.exit(1)
	if not changed:
		print(f"ERROR: no Status line found in {task_id}'s block", file=sys.stderr)
		sys.exit(1)

	with open(path, "w", encoding="utf-8") as f:
		f.writelines(out)


def main():
	if len(sys.argv) < 3:
		print(
			"Usage: tasks.py select <TASKS_FILE> | tasks.py waiting <TASKS_FILE> | tasks.py set-status <TASKS_FILE> <TASK_ID> <STATUS>",
			file=sys.stderr,
		)
		sys.exit(2)

	cmd = sys.argv[1]
	if cmd == "select":
		path = sys.argv[2]
		tasks = parse(path)
		print(select_next(tasks))
	elif cmd == "waiting":
		for line in waiting_report(parse(sys.argv[2])):
			print(line)
	elif cmd == "set-status":
		if len(sys.argv) != 5:
			print(
				"Usage: tasks.py set-status <TASKS_FILE> <TASK_ID> <STATUS>",
				file=sys.stderr,
			)
			sys.exit(2)
		_, _, path, task_id, status = sys.argv
		set_status(path, task_id, status)
		print(f"{task_id} -> {status}")
	else:
		print(f"Unknown command: {cmd}", file=sys.stderr)
		sys.exit(2)


if __name__ == "__main__":
	main()
