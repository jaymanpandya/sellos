#!/usr/bin/env python3
"""Fails when the provisioner's MariaDB password is in a file it must never reach (SOS-SETUP-18).

Usage: check_no_secret_leak.py [--since EPOCH] PATH [PATH ...]

The password is read from SELLOS_DB_PROVISIONER_PASSWORD in the environment, never from argv. Every
file under each PATH (a file or a folder; a missing one is skipped) is searched for it, except .git
and node_modules folders. With --since, only files changed at or after that time are searched, so
a log that was clean when the task started is searched only if something wrote to it.

A hit prints the file and line number, never the value, and exits 1. With no password set there is
nothing to find, and it exits 0. scripts/run-tests.sh runs it at the end of every gate run over the
gate's log folder, the bench's logs (the bench CLI writes every command line it runs to
logs/bench.log, so a password passed to `bench new-site` lands there), the shared site config, the
tenant site folders, the repository and the agent's session transcripts.
"""

import os
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules"}
CHUNK = 1 << 20


def files_under(path):
	if path.is_file():
		yield path
		return
	if not path.is_dir():
		return
	for root, dirs, names in os.walk(path):
		dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
		for name in names:
			yield Path(root) / name


def hit_lines(path, needle):
	"""Line numbers of path that hold needle. Reads in chunks, so a big log is not loaded at once."""
	lines, line_no, tail = [], 1, b""
	try:
		# A path the gate passes in, not user input.
		with open(path, "rb") as f:  # nosemgrep
			while chunk := f.read(CHUNK):
				data = tail + chunk
				start = 0
				while (i := data.find(needle, start)) != -1:
					n = line_no + data.count(b"\n", 0, i)
					if not lines or lines[-1] != n:
						lines.append(n)
					start = i + 1
				keep = max(len(needle) - 1, 0)
				cut = len(data) - keep
				line_no += data.count(b"\n", 0, cut)
				tail = data[cut:]
	except OSError:
		return []
	return lines


def leaks(paths, needle, since=None):
	found = []
	for top in paths:
		for path in files_under(Path(top)):
			try:
				if not path.is_file() or (since is not None and path.stat().st_mtime < since):
					continue
			except OSError:
				continue
			for n in hit_lines(path, needle):
				found.append(f"{path}:{n}")
	return found


def main(argv):
	since = None
	if argv[:1] == ["--since"]:
		since = float(argv[1])
		argv = argv[2:]
	if not argv:
		print(__doc__.split("\n\n")[1])
		return 2
	secret = os.environ.get("SELLOS_DB_PROVISIONER_PASSWORD", "")
	if not secret:
		print("Secret leak check: SELLOS_DB_PROVISIONER_PASSWORD is not set, so there is nothing to find.")
		return 0
	found = leaks(argv, secret.encode(), since)
	if found:
		print("Secret leak check FAILED. The provisioner's MariaDB password is written in:")
		for line in found:
			print(f"  {line}")
		print(
			"Remove it from those files. Get it with get_provisioner_password() and hand it only to Frappe's"
		)
		print(
			"new-site and drop-site through a child process's environment (sellos.provisioning.tenant_sites),"
		)
		print("never on a command line, never through the bench wrapper (it logs its command line), a")
		print("print, a log, an exception message, a config file or a test fixture.")
		return 1
	print("Secret leak check: the provisioner's password is in none of the searched files.")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
