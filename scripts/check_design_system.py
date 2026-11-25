#!/usr/bin/env python3
"""Design system check (docs/DESIGN_SYSTEM.md, rule 6): a page is assembled from the shared pieces.

It fails when a page draws its own button, card, heading, radius, padding, shadow, font size or colour. A
"page" is every .vue file under frontend/src outside frontend/src/components (the shared pieces) and outside
frontend/src/theme. Pages may use layout utilities (flex, grid, gap, margin, width, overflow, truncate...) and
the named text roles of the system (ui-text-*, ui-link); everything that decides how a thing looks lives in a
shared piece or in the tokens.

    python3 scripts/check_design_system.py            check every page, list every finding, exit 1 on any
    python3 scripts/check_design_system.py --list     the same list, exit 0 (to see what fails)
    python3 scripts/check_design_system.py FILE...    check only these files (pre-commit)

docs/design-system-backlog.txt lists pages that still fail, as `path` lines. A page not on it that fails is an
error; a page on it that passes must come off it. The list only shrinks, and it is empty at the end of the pass.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"
BACKLOG = ROOT / "docs" / "design-system-backlog.txt"
SHARED = SRC / "components"
SKIP = (SRC / "theme", SHARED)

BLANK = re.compile(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", re.S)
CLASS_ATTR = re.compile(r"""(?:class|:class)\s*=\s*("[^"]*"|'[^']*')""", re.S)
TOKEN = re.compile(r"[^\s\"'`${}()?:+\[\],|&!]+(?:\[[^\]]*\])?")

RAW_CONTROL = re.compile(r"<(button|input|select|textarea)(?=[\s/>])")
HEADING = re.compile(r"<h[1-6](?=[\s/>])")
STYLE_ATTR = re.compile(r"""\sstyle\s*=|:style\s*=""")
COLOUR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")

# A colour utility: text, background, border, ring... in an ink, brand, surface, status or palette colour, or an area.
COLOUR_UTILITY = re.compile(
	r"^!?(text|bg|border|ring|fill|stroke|divide|outline|decoration|from|to|via)-"
	r"(ink|brand|surface|line|tone|danger|accent|link|ghost|on-brand|white|black|"
	r"gray|grey|red|green|blue|amber|yellow|orange|slate|zinc|neutral|teal|indigo|purple|pink|"
	r"area|sales|calls|inventory|money|company)(-.*)?$"
)

# Utility classes a page may not write: they decide how something looks.
FORBIDDEN = [
	("radius", re.compile(r"^!?rounded(-.*)?$")),
	("shadow", re.compile(r"^!?shadow(-.*)?$")),
	(
		"font size",
		re.compile(r"^!?text-(xs|sm|base|lg|xl|[2-9]xl|title|heading|stat|\[.*\])$"),
	),
	("font weight", re.compile(r"^!?font-(thin|light|normal|medium|semibold|bold|extrabold|black|heading)$")),
	("padding", re.compile(r"^!?-?p[xytblrse]?-.*$")),
	("colour", COLOUR_UTILITY),
	(
		"own card",
		re.compile(r"^(ui-card|ui-card-heading|ui-table-card|ui-field|ui-button|ui-badge(-.*)?|btn)$"),
	),
	("own heading", re.compile(r"^(ui-page-title|ui-page-lead)$")),
]


def pages():
	for path in sorted(SRC.rglob("*.vue")):
		if any(path.is_relative_to(s) for s in SKIP):
			continue
		yield path


def blank(text):
	return BLANK.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def findings(path):
	"""[(line, rule, text)] for one file."""
	text = path.read_text(encoding="utf-8")
	template = blank(text)
	found = []

	def line_of(pos):
		return template.count("\n", 0, pos) + 1

	for m in RAW_CONTROL.finditer(template):
		found.append((line_of(m.start()), "own control", f"<{m.group(1)}>"))
	for m in HEADING.finditer(template):
		found.append((line_of(m.start()), "own heading", m.group(0) + ">"))
	for m in STYLE_ATTR.finditer(template):
		found.append((line_of(m.start()), "inline style", "style attribute"))
	for m in COLOUR_LITERAL.finditer(template):
		found.append((line_of(m.start()), "colour", m.group(0)))
	for attr in CLASS_ATTR.finditer(template):
		for token in TOKEN.findall(attr.group(1)):
			for rule, pattern in FORBIDDEN:
				if pattern.match(token):
					found.append((line_of(attr.start()), rule, token))
					break
	return sorted(set(found))


def backlog():
	if not BACKLOG.exists():
		return set()
	lines = (l.split("#", 1)[0].strip() for l in BACKLOG.read_text(encoding="utf-8").splitlines())
	return {l for l in lines if l}


def main(argv):
	listing = "--list" in argv
	files = [Path(a).resolve() for a in argv if not a.startswith("--")]
	targets = (
		[
			f
			for f in files
			if f.suffix == ".vue" and f.is_relative_to(SRC) and not any(f.is_relative_to(s) for s in SKIP)
		]
		if files
		else list(pages())
	)
	if files and not targets:
		return 0
	listed = backlog()
	failing = {}
	for path in targets:
		hits = findings(path)
		if hits:
			failing[path.relative_to(ROOT).as_posix()] = hits
	bad = 0
	for rel, hits in sorted(failing.items()):
		counts = {}
		for _, rule, _ in hits:
			counts[rule] = counts.get(rule, 0) + 1
		summary = ", ".join(f"{n} {r}" for r, n in sorted(counts.items()))
		known = rel in listed
		if listing or not known:
			print(f"{'BACKLOG ' if known else 'FAIL    '}{rel}: {summary}")
			if (listing and "--detail" in argv) or not known:
				for line, rule, what in hits[:12]:
					print(f"    {rel}:{line}: {rule}: {what}")
		if not known:
			bad += 1
	if not files:
		for rel in sorted(listed - set(failing)):
			print(f"STALE   {rel}: passes now, remove it from docs/design-system-backlog.txt")
			bad += 1
	if listing:
		print(f"{len(failing)} of {len(targets)} pages fail")
		return 0
	if bad:
		print(
			"GUARD FAILED: design system\nFix: build the page from the shared pieces in frontend/src/components "
			"and the tokens (docs/DESIGN_SYSTEM.md). Never write a button, card, heading, radius, padding, shadow, "
			"font size or colour on a page; extend the piece instead."
		)
		return 1
	print(f"Design system check: {len(targets)} pages clean ({len(listed)} on the backlog).")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
