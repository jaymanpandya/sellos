#!/usr/bin/env python3
"""Check that the SellOS server LaunchAgent runs only the pinned serve command (SOS-SETUP-34).

  launch_agent_check.py <plist>

The plist's ProgramArguments must be /bin/bash -c "cd <bench> && exec <bench> " followed by
the pinned command, --site sellos_test.localhost serve --port 8004, and nothing in it may run a serve
without that site: a serve with no --site falls back to default_site and serves BuildOS's site for
every host name (CLAUDE.md, Working rules). Exit 0 and print "pinned" when it is; exit 1 with the
reason when not.
"""

import plistlib
import re
import sys
from pathlib import Path

LABEL = "com.sellos.server"
PINNED = "--site sellos_test.localhost serve --port 8004"
COMMAND = re.compile(r'^cd "[^"]+" && exec "[^"]*/bench" ' + re.escape(PINNED) + r"$")


def problems(path):
	try:
		data = plistlib.loads(Path(path).read_bytes())
	except (OSError, plistlib.InvalidFileException, ValueError) as e:
		return [f"{path} cannot be read as a plist: {e}"]
	found = []
	if data.get("Label") != LABEL:
		found.append(f"Label is {data.get('Label')!r}, not {LABEL!r}")
	args = data.get("ProgramArguments") or []
	if len(args) != 3 or args[:2] != ["/bin/bash", "-c"] or not COMMAND.match(args[2]):
		found.append(f"ProgramArguments is {args!r}, not /bin/bash -c 'cd <bench> && exec <bench> {PINNED}'")
	text = " ".join(str(a) for a in args)
	for m in re.finditer(r"\bserve\b", text):
		if not text[: m.end()].endswith("--site sellos_test.localhost serve") or not text[
			m.end() :
		].startswith(" --port 8004"):
			found.append(f"an unpinned serve command: {text!r}")
			break
	return found


def main(argv):
	if len(argv) != 1:
		print(__doc__, file=sys.stderr)
		return 2
	found = problems(argv[0])
	if found:
		print("\n".join(found))
		return 1
	print(f"pinned: {PINNED}")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
