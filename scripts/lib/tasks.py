#!/usr/bin/env python3
"""Shared TASKS.md parsing and mutation helpers for the SellOS build loop.

Zero LLM calls. Deterministic. Mirrors the JarvisCodes/OTT task selection
logic documented for that build:

  1. If any task is already "In Progress", resume that one first.
  2. Otherwise pick, among the "Not Started" tasks whose Dependencies are
     all satisfied, the one in the earliest Launch tier (Dec 20 before
     Jan 1), and within a tier the first in file order. A dependency is
     satisfied when it is "Complete" or "Not Needed" (SOS-SETUP-19).
  3. If nothing is eligible, report NONE_ELIGIBLE.

A "Not Needed" task is never picked and never reported: not in the
Blocked list, not in the Waiting report.

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
LAUNCH_RE = re.compile(r"^-\s*\*\*Launch:\*\*\s*(?P<value>.*)$")

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6}
# The launch tiers, earliest first (SOS-SETUP-19). A task with no tier, or one not listed here, is
# picked after every tier.
LAUNCH_RANK = {"dec 20": 0, "jan 1": 1}
NOT_NEEDED = "Not Needed"
SATISFIED = {"Complete", NOT_NEEDED}


def launch_rank(value):
	return LAUNCH_RANK.get(" ".join(value.lower().replace(",", " ").split()[:2]), 9)


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
			current = {
				"id": m.group("id"),
				"status": "",
				"priority": "",
				"owner": "",
				"launch": "",
				"deps": [],
			}
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
		m = LAUNCH_RE.match(line.strip())
		if m:
			current["launch"] = m.group("value").strip()
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

	satisfied = {t["id"] for t in tasks if t["status"] in SATISFIED}

	# Tier first, then dependencies, then file order (SOS-SETUP-19). Priority no longer orders.
	best = None
	best_rank = None
	for t in tasks:
		if t["status"] != "Not Started":
			continue
		if not all(d in satisfied for d in t["deps"]):
			continue
		rank = launch_rank(t["launch"])
		if best is None or rank < best_rank:
			best = t
			best_rank = rank
	return best["id"] if best else "NONE_ELIGIBLE"


def pick_order(tasks, limit=None):
	"""The order the loop would pick tasks in, if every task it picked then passed the gate.

	Waiting and Parked tasks are never completed here, so tasks that depend on them are left out.
	"""
	state = [dict(t) for t in tasks]
	order = []
	while limit is None or len(order) < limit:
		picked = select_next(state)
		if picked == "NONE_ELIGIBLE" or picked.startswith("BLOCKED_EXISTS:"):
			break
		order.append(picked)
		for t in state:
			if t["id"] == picked:
				t["status"] = "Complete"
	return order


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
			if d not in by_id or by_id[d]["status"] not in SATISFIED
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
			"Usage: tasks.py select <TASKS_FILE> | tasks.py order <TASKS_FILE> [N] | tasks.py waiting <TASKS_FILE> | tasks.py set-status <TASKS_FILE> <TASK_ID> <STATUS>",
			file=sys.stderr,
		)
		sys.exit(2)

	cmd = sys.argv[1]
	if cmd == "select":
		path = sys.argv[2]
		tasks = parse(path)
		print(select_next(tasks))
	elif cmd == "order":
		limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
		for task_id in pick_order(parse(sys.argv[2]), limit):
			print(task_id)
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
