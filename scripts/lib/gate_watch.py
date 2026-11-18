#!/usr/bin/env python3
"""A hung or frozen gate must be impossible to miss and impossible to leave stuck (SOS-SETUP-39).

On 17 November 2026 the gate held the bench lock for 5 hours after the Mac slept on battery power: no
output, no Telegram message, and no latest.log. Three commands fix that.

  gate_watch.py run [--label L] [--timeout S] [--stall S --stall-file F] [--fault-file F] -- cmd ...
      Run cmd in its own session and watch it by the wall clock (a sleep counts: the clock that stops
      during a sleep is deliberately not used). When the run lasts longer than --timeout seconds, or
      the --stall-file has not been written for --stall seconds, kill SellOS's own process tree (cmd
      and everything below it, never anything else), release the bench gate lock if a killed process
      held it, write the reason to --fault-file, and exit 124 (timeout) or 125 (stall). Otherwise it
      exits with cmd's own status. A TERM or INT sent to this process kills the tree and exits 143,
      so "sellos stop --now" leaves no gate behind.

  gate_watch.py cleanup --tag T
      Kill leftover Cypress and headless Chrome processes that belong to SellOS and nothing else. A
      process is SellOS's when its environment holds SELLOS_GATE_TAG=T: the loop and the gate export
      it, every child inherits it, and it survives when the parent dies and the child is adopted by
      launchd. BuildOS's and Pamaa's Cypress, and Jayman's own Chrome, have no such variable, so
      they are never matched, whatever their names are.

  gate_watch.py power [--warn]
      One line about the power source and the charge. With --warn, exit 1 when the Mac is on battery
      power or below 30 percent, so the caller can warn. SELLOS_PMSET_FILE holds pmset's output in
      the tests.
"""

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

TIMEOUT_EXIT = 124
STALL_EXIT = 125
LOW_BATTERY_PERCENT = 30
GRACE_SECONDS = 5.0

# A Cypress process by name, or an Electron or Chrome process Cypress started headless.
CYPRESS_RE = re.compile(r"cypress", re.IGNORECASE)
BROWSER_RE = re.compile(r"chrome|chromium|electron", re.IGNORECASE)
HEADLESS_RE = re.compile(r"--headless")


def ps(*args):
	return subprocess.run(["ps", *args], capture_output=True, text=True, check=False).stdout.splitlines()


def children_map():
	table = {}
	for line in ps("-axo", "pid=,ppid="):
		parts = line.split()
		if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
			table.setdefault(int(parts[1]), []).append(int(parts[0]))
	return table


def descendants(root):
	table = children_map()
	found, queue = [], [root]
	while queue:
		for child in table.get(queue.pop(), []):
			if child not in found:
				found.append(child)
				queue.append(child)
	return found


def alive(pid):
	try:
		os.kill(pid, 0)
	except ProcessLookupError:
		return False
	except PermissionError:
		return True
	return True


def signal_all(pids, sig):
	for pid in pids:
		try:
			os.kill(pid, sig)
		except (ProcessLookupError, PermissionError):
			pass


def kill_tree(root, grace=GRACE_SECONDS):
	"""TERM, then KILL, the process and everything below it. Returns every pid it signalled."""
	seen = set()
	pids = [*descendants(root), root]
	seen.update(pids)
	signal_all(reversed(pids), signal.SIGTERM)
	deadline = time.time() + grace
	while time.time() < deadline and any(alive(p) for p in seen):
		time.sleep(0.1)
	# Anything started during the grace period is below the same root, or was adopted by launchd.
	late = [p for p in descendants(root) if p not in seen]
	seen.update(late)
	survivors = [p for p in seen if alive(p)]
	signal_all(survivors, signal.SIGKILL)
	return seen


def release_bench_lock(killed):
	"""Release the bench gate lock when a killed process held it, or when its holder is already dead."""
	lock = Path(os.environ.get("BENCH_GATE_LOCK_DIR", "/tmp/iespl-bench-heavy.lock.d"))
	try:
		holder = int((lock / "pid").read_text(encoding="utf-8").strip())
	except (OSError, ValueError):
		return False
	if holder in killed or not alive(holder):
		shutil.rmtree(lock, ignore_errors=True)
		print(f"Released the bench gate lock (held by pid {holder}).", flush=True)
		return True
	return False


def write_fault(path, text):
	if not path:
		return
	try:
		Path(path).parent.mkdir(parents=True, exist_ok=True)
		Path(path).write_text(text + "\n", encoding="utf-8")
	except OSError:
		pass


def newest(path, started):
	try:
		return max(os.stat(path).st_mtime, started)
	except OSError:
		return started


def run(args):
	command = args.command[1:] if args.command[:1] == ["--"] else args.command
	if not command:
		print("gate_watch.py run: no command given", file=sys.stderr)
		return 2
	started = time.time()
	proc = subprocess.Popen(command, start_new_session=True)

	def forward(signum, _frame):
		kill_tree(proc.pid)
		sys.exit(128 + signum)

	signal.signal(signal.SIGTERM, forward)
	signal.signal(signal.SIGINT, forward)
	signal.signal(signal.SIGHUP, forward)

	reason, code = "", 0
	while True:
		status = proc.poll()
		if status is not None:
			return status if status >= 0 else 128 - status
		now = time.time()
		if args.timeout and now - started > args.timeout:
			reason = (
				f"{args.label} ran longer than its limit of {args.timeout // 60} min ({int(now - started)} s)"
			)
			code = TIMEOUT_EXIT
			break
		if args.stall and args.stall_file and now - newest(args.stall_file, started) > args.stall:
			quiet = int(now - newest(args.stall_file, started))
			reason = (
				f"{args.label} wrote nothing to {args.stall_file} for {quiet // 60} min "
				f"(limit {args.stall // 60} min); the Mac may have slept or a process hung"
			)
			code = STALL_EXIT
			break
		time.sleep(args.poll)

	print(f"GATE TIMEOUT: {reason}. Killing its process tree.", flush=True)
	killed = kill_tree(proc.pid)
	try:
		proc.wait(timeout=GRACE_SECONDS)
	except subprocess.TimeoutExpired:
		pass
	release_bench_lock(killed)
	write_fault(args.fault_file, f"gate timeout: {reason}")
	return code


def command_table():
	"""pid -> command line, without the environment."""
	table = {}
	for line in ps("-axwwo", "pid=,command="):
		parts = line.strip().split(None, 1)
		if len(parts) == 2 and parts[0].isdigit():
			table[int(parts[0])] = parts[1]
	return table


def tagged_pids(tag):
	"""The pids whose environment holds SELLOS_GATE_TAG=<tag>, on macOS (ps -E, which appends the
	environment to the command) and on Linux (/proc/<pid>/environ)."""
	wanted = f"SELLOS_GATE_TAG={tag}"
	found = set()
	if sys.platform == "darwin":
		marker = re.compile(r"(?:^|\s)" + re.escape(wanted) + r"(?:\s|$)")
		for line in ps("-axwwE", "-o", "pid=,command="):
			parts = line.strip().split(None, 1)
			if len(parts) == 2 and parts[0].isdigit() and marker.search(parts[1]):
				found.add(int(parts[0]))
		return found
	for entry in Path("/proc").iterdir():
		if not entry.name.isdigit():
			continue
		try:
			variables = (entry / "environ").read_bytes().split(b"\0")
		except OSError:
			continue
		if wanted.encode() in variables:
			found.add(int(entry.name))
	return found


def own_chain():
	chain, pid = set(), os.getpid()
	parents = {}
	for line in ps("-axo", "pid=,ppid="):
		parts = line.split()
		if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
			parents[int(parts[0])] = int(parts[1])
	while pid and pid not in chain:
		chain.add(pid)
		pid = parents.get(pid, 0)
	return chain


def is_browser_automation(command):
	return bool(CYPRESS_RE.search(command)) or (
		bool(BROWSER_RE.search(command)) and bool(HEADLESS_RE.search(command))
	)


def leftovers(tag):
	"""(pid, command) of SellOS's own Cypress and headless Chrome processes."""
	mine = tagged_pids(tag) - own_chain()
	return [
		(pid, command)
		for pid, command in command_table().items()
		if pid in mine and is_browser_automation(command)
	]


def cleanup(args):
	if not args.tag:
		print(
			"gate_watch.py cleanup: --tag is required, so that nothing but SellOS's own is killed",
			file=sys.stderr,
		)
		return 2
	found = leftovers(args.tag)
	for pid, command in found:
		print(f"Killing a leftover of SellOS's own: pid {pid}: {command[:100]}", flush=True)
	if found:
		pids = [pid for pid, _ in found]
		signal_all(pids, signal.SIGTERM)
		deadline = time.time() + 3
		while time.time() < deadline and any(alive(p) for p in pids):
			time.sleep(0.1)
		signal_all([p for p in pids if alive(p)], signal.SIGKILL)
	return 0


def power_state():
	"""(source, percent): source is 'ac', 'battery' or None; percent is an int or None."""
	override = os.environ.get("SELLOS_PMSET_FILE")
	if override:
		text = Path(override).read_text(encoding="utf-8")
	else:
		try:
			text = subprocess.run(
				["pmset", "-g", "batt"], capture_output=True, text=True, check=False, timeout=10
			).stdout
		except (OSError, subprocess.TimeoutExpired):
			return None, None
	source = None
	if re.search(r"drawing from 'Battery Power'", text):
		source = "battery"
	elif re.search(r"drawing from 'AC Power'", text):
		source = "ac"
	percent = re.search(r"(\d+)%", text)
	return source, int(percent.group(1)) if percent else None


def power(args):
	source, percent = power_state()
	label = {"ac": "on AC power", "battery": "on battery power"}.get(source, "power source unknown")
	line = f"{label}{f', {percent}%' if percent is not None else ''}"
	low = percent is not None and percent < LOW_BATTERY_PERCENT
	print(line)
	return 1 if args.warn and (source == "battery" or low) else 0


def main(argv):
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	sub = parser.add_subparsers(dest="cmd", required=True)
	r = sub.add_parser("run")
	r.add_argument("--label", default="the command")
	r.add_argument("--timeout", type=int, default=0)
	r.add_argument("--stall", type=int, default=0)
	r.add_argument("--stall-file", default="")
	r.add_argument("--fault-file", default="")
	r.add_argument("--poll", type=float, default=1.0)
	r.add_argument("command", nargs=argparse.REMAINDER)
	c = sub.add_parser("cleanup")
	c.add_argument("--tag", default="")
	p = sub.add_parser("power")
	p.add_argument("--warn", action="store_true")
	args = parser.parse_args(argv)
	return {"run": run, "cleanup": cleanup, "power": power}[args.cmd](args)


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
