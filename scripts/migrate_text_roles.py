#!/usr/bin/env python3
"""One off helper for the design system pass: rewrite the text colour, size and weight utilities of a page into the
named text roles (docs/DESIGN_SYSTEM.md, rule 5), so the page stops writing a font size, weight or colour.

    python3 scripts/migrate_text_roles.py frontend/src/pages/UsersPage.vue ...

It only touches class strings. A class string that keeps a utility the check refuses (a radius, padding, a heading
size) is left for the person to fix by hand; `python3 scripts/check_design_system.py --list --detail` shows what
is left.
"""

import re
import sys
from pathlib import Path

CONSUMED = re.compile(
	r"^!?(text-(sm|xs|base|ink|ink-muted|ink-body|danger|accent|tone-danger|tone-warning|tone-success|tone-info|tone-neutral)|font-(medium|semibold|bold))$"
)


def role(tokens):
	has = set(tokens)
	if has & {"text-danger", "text-accent", "text-tone-danger"}:
		return "ui-text-error"
	if "text-tone-warning" in has:
		return "ui-text-warning"
	if "text-tone-success" in has:
		return "ui-text-success"
	if "text-ink-muted" in has:
		return "ui-text-muted"
	strong = bool(has & {"font-medium", "font-semibold", "font-bold"})
	small = bool(has & {"text-sm", "text-xs"})
	if strong and not small:
		return "ui-text-strong"
	if "text-ink-body" in has:
		return "ui-text-small" if small else "ui-text-secondary"
	if small:
		return "ui-text-strong" if strong else "ui-text-small"
	if "text-ink" in has:
		return "ui-text-strong" if strong else "ui-text-body"
	if strong:
		return "ui-text-strong"
	return None


def rewrite(literal):
	tokens = literal.split()
	if not any(CONSUMED.match(t) for t in tokens):
		return literal
	chosen = role(tokens)
	kept = [t for t in tokens if not CONSUMED.match(t)]
	# A responsive or state prefixed variant (md:text-sm, hover:text-ink) is not a plain role: keep the literal.
	if chosen and not any(t.startswith("ui-text-") for t in kept):
		kept.append(chosen)
	return " ".join(kept)


CLASS = re.compile(r'(?P<attr>:?class)=(?P<q>["\'])(?P<val>.*?)(?P=q)', re.S)
LITERAL = re.compile(r"'([^']*)'")


def migrate(text):
	def fix(match):
		attr, quote, value = match.group("attr"), match.group("q"), match.group("val")
		if attr == ":class":
			value = LITERAL.sub(lambda m: "'" + rewrite(m.group(1)) + "'", value)
		else:
			value = rewrite(value)
		return f"{attr}={quote}{value}{quote}"

	# Only the template: the script block is left alone.
	head, sep, tail = text.partition("<script")
	return CLASS.sub(fix, head) + sep + tail


def main(paths):
	for name in paths:
		path = Path(name)
		text = path.read_text(encoding="utf-8")
		new = migrate(text)
		if new != text:
			path.write_text(new, encoding="utf-8")
			print("migrated", name)
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
