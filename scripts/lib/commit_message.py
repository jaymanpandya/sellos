#!/usr/bin/env python3
"""Take every CI skip marker out of a commit message the loop makes (SOS-SETUP-34).

On 13 November 2026 a commit message named "[skip ci]" in passing, GitHub skipped CI on it, and the
red test it carried was found only on the next push. Every commit the loop makes, from the task title,
the agent's summary or the loop's own text, goes through this first, so no loop commit ever skips CI.

Removed, in any case and with any spacing, hyphen or underscore inside the brackets: [skip ci],
[ci skip], [no ci], [skip actions], [actions skip], [skip checks]; a "skip-checks: true" (or
skip-checks:true, skip_checks = true) line or phrase; and ***NO_CI***.

  commit_message.py clean            the message on stdin, the clean message on stdout
  commit_message.py clean-file <f>   rewrite the file in place
"""

import re
import sys
from pathlib import Path

SEP = r"[\s_-]*"
MARKERS = (
	re.compile(
		r"\[\s*(?:skip"
		+ SEP
		+ r"(?:ci|actions|checks)|(?:ci|actions)"
		+ SEP
		+ r"skip|no"
		+ SEP
		+ r"ci)\s*\]",
		re.IGNORECASE,
	),
	re.compile(r"skip" + SEP + r"checks\s*[:=]\s*\S*", re.IGNORECASE),
	re.compile(r"\*{3}\s*NO_CI\s*\*{3}", re.IGNORECASE),
)


def clean(message):
	lines = []
	for line in message.splitlines():
		new = line
		for marker in MARKERS:
			new = marker.sub("", new)
		if new != line:
			new = re.sub(r"[ \t]{2,}", " ", new).rstrip()
			new = re.sub(r"\s+([,.;:)])", r"\1", new)
			if not new.strip():
				continue
		lines.append(new)
	return "\n".join(lines).strip("\n") + "\n"


def main(argv):
	if argv == ["clean"]:
		sys.stdout.write(clean(sys.stdin.read()))
		return 0
	if len(argv) == 2 and argv[0] == "clean-file":
		path = Path(argv[1])
		path.write_text(clean(path.read_text(encoding="utf-8")), encoding="utf-8")
		return 0
	print(__doc__, file=sys.stderr)
	return 2


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
