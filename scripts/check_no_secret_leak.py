#!/usr/bin/env python3
"""Fails when a loop secret is in a file it must never reach (SOS-SETUP-18, SOS-SETUP-29).

Usage: check_no_secret_leak.py [--since EPOCH] PATH [PATH ...]

The secrets are the values of these environment variables, read from the environment, never from
argv:
  SELLOS_DB_PROVISIONER_PASSWORD   the MariaDB provisioner's password
  SELLOS_TELEGRAM_BOT_TOKEN        the loop's Telegram bot token
  SELLOS_TELEGRAM_CHAT_ID          the loop's Telegram chat
  BUILDOS_*                        every BuildOS variable whose name is a Telegram setting or looks
                                   like a credential (TOKEN, PASSWORD, SECRET, ...). BuildOS's other
                                   variables (its app name, branch, site, bench folder) are plain
                                   words and paths that rightly appear in logs, so they are not
                                   searched; the agent never gets them (scripts/lib/db_secrets.sh).
A Telegram or BuildOS value shorter than 6 characters is not searched for, because it would be found
everywhere; the check says so by name.

Every file under each PATH (a file or a folder; a missing one is skipped) is searched, except .git
and node_modules folders. With --since, only files changed at or after that time are searched, so
a log that was clean when the task started is searched only if something wrote to it.

A hit prints the file, line number and variable name, never the value, and exits 1. With none of
them set there is nothing to find, and it exits 0. scripts/run-tests.sh runs it at the end of every
gate run over the gate's log folder, the bench's logs (the bench CLI writes every command line it
runs to logs/bench.log, so a password passed to `bench new-site` lands there), the shared site
config, the tenant site folders, the repository and the agent's session transcripts.
"""

import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules"}
CHUNK = 1 << 20
PROVISIONER = "SELLOS_DB_PROVISIONER_PASSWORD"
TELEGRAM = ("SELLOS_TELEGRAM_BOT_TOKEN", "SELLOS_TELEGRAM_CHAT_ID")
BUILDOS_SECRET = re.compile(
	r"^BUILDOS_.*(TELEGRAM|PASSWORD|PASSWD|SECRET|TOKEN|CREDENTIAL|API_KEY|ACCESS_KEY|PRIVATE_KEY)"
)
MIN_LENGTH = 6


def secrets(env):
	"""(name -> value bytes) to search for, and the names skipped because their value is too short."""
	found, short = {}, []
	if env.get(PROVISIONER):
		found[PROVISIONER] = env[PROVISIONER].encode()
	names = [*TELEGRAM, *sorted(n for n in env if BUILDOS_SECRET.match(n))]
	for name in names:
		value = env.get(name, "")
		if not value:
			continue
		if len(value) < MIN_LENGTH:
			short.append(name)
			continue
		found[name] = value.encode()
	return found, short


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


def hit_lines(path, needles):
	"""(line number, name) for each needle in path. Reads in chunks, so a big log is not loaded at once."""
	hits, line_no, tail = [], 1, b""
	keep = max((len(v) for v in needles.values()), default=1) - 1
	try:
		# A path the gate passes in, not user input.
		with open(path, "rb") as f:  # nosemgrep
			while chunk := f.read(CHUNK):
				data = tail + chunk
				for name, needle in needles.items():
					start = 0
					while (i := data.find(needle, start)) != -1:
						hit = (line_no + data.count(b"\n", 0, i), name)
						if hit not in hits:
							hits.append(hit)
						start = i + 1
				cut = len(data) - keep
				line_no += data.count(b"\n", 0, cut)
				tail = data[cut:]
	except OSError:
		return []
	return sorted(hits)


def leaks(paths, needles, since=None):
	found = []
	for top in paths:
		for path in files_under(Path(top)):
			try:
				if not path.is_file() or (since is not None and path.stat().st_mtime < since):
					continue
			except OSError:
				continue
			for n, name in hit_lines(path, needles):
				found.append((f"{path}:{n}", name))
	return found


def main(argv):
	since = None
	if argv[:1] == ["--since"]:
		since = float(argv[1])
		argv = argv[2:]
	if not argv:
		print(__doc__.split("\n\n")[1])
		return 2
	needles, short = secrets(os.environ)
	for name in short:
		print(
			f"Secret leak check: {name} is shorter than {MIN_LENGTH} characters, so it is not searched for."
		)
	if not needles:
		print(
			"Secret leak check: SELLOS_DB_PROVISIONER_PASSWORD, the Telegram variables and the BuildOS"
			" credentials are not set, so there is nothing to find."
		)
		return 0
	found = leaks(argv, needles, since)
	if found:
		print("Secret leak check FAILED. A secret's value is written in:")
		for place, name in found:
			print(f"  {place} (the value of {name})")
		if any(name == PROVISIONER for _, name in found):
			print(
				"The provisioner's password: get it with get_provisioner_password() and hand it only to"
				" Frappe's new-site and drop-site through a child process's environment"
				" (sellos.provisioning.tenant_sites), never on a command line, never through the bench"
				" wrapper (it logs its command line), a print, a log, an exception message, a config file"
				" or a test fixture."
			)
		if any(name != PROVISIONER for _, name in found):
			print(
				"A Telegram or BuildOS value: only scripts/notify-telegram.sh uses the Telegram values, and"
				" never prints them. Nothing in SellOS reads a BUILDOS_ variable. Remove the value from"
				" those files."
			)
		return 1
	print(f"Secret leak check: none of {', '.join(needles)} is in the searched files.")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
