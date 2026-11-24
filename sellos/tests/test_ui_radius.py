"""SOS-LOOP (design system pass, 25 November 2026): three radii and no others.

docs/DESIGN_SYSTEM.md, section 1: a card radius of 14px (cards, panels, dialogs, menus), a control radius of 10px
(buttons, fields, selects, sidebar items, small chips) and fully round (icon badges, avatars, status pills, count
badges). This test reads the web app's source and the two public pages and fails when anything uses another radius:
a Tailwind `rounded-*` size other than `rounded-card`, `rounded-control` and `rounded-round`, a `border-radius` that
is not one of the tokens, or a theme that defines a fourth. `cypress/integration/frontend/ui_radius.cy.js` checks
the same on the rendered pages. (The first layout pass of 24 November had one radius for everything; the source
document replaced that rule.)
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"
PUBLIC_PAGES = [
	REPO_ROOT / "sellos" / "public" / "css" / "sellos_login.css",
	REPO_ROOT / "sellos" / "www" / "enquiry.html",
]
THEME_TOKENS = FRONTEND / "theme" / "tokens.js"
SOURCE_SUFFIXES = {".vue", ".css", ".js", ".html"}

# `rounded`, `rounded-pill`, `rounded-none` and the side forms `rounded-t`, `rounded-b`, `rounded-l`,
# `rounded-r` use the one radius. Every sized name is another radius.
BAD_CLASS = re.compile(
	r"(?<![\w-])!?rounded(?:-(?:[tblr]|tl|tr|bl|br|s|e))?-(?:sm|md|lg|xl|2xl|3xl|full|input|badge|pill|\[[^\]]*\])(?![\w-])"
)
RADIUS_DECLARATION = re.compile(r"border(?:-(?:top|bottom)-(?:left|right))?-radius\s*:\s*([^;}\"']+)")
ALLOWED_VALUES = {
	"0",
	"var(--radius-card)",
	"var(--radius-control)",
	"var(--radius-round)",
	"14px",
	"10px",
	"inherit",
}


def source_files():
	for path in sorted(FRONTEND.rglob("*")):
		if path.suffix in SOURCE_SUFFIXES and "fonts" not in path.parts:
			yield path
	yield from PUBLIC_PAGES


class TestOneRadius(unittest.TestCase):
	"""SOS-LOOP design system pass: card 14px, control 10px, round."""

	def test_no_other_rounded_class(self):
		found = []
		for path in source_files():
			if path == THEME_TOKENS:  # its comment names the frappe-ui sizes it maps to the one radius
				continue
			for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
				for match in BAD_CLASS.finditer(line):
					found.append(f"{path.relative_to(REPO_ROOT)}:{n}: {match.group(0)}")
		self.assertEqual(found, [], "Use rounded-card (14px), rounded-control (10px) or rounded-round.")

	def test_no_other_border_radius_value(self):
		found = []
		for path in source_files():
			for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
				for match in RADIUS_DECLARATION.finditer(line):
					if match.group(1).strip() not in ALLOWED_VALUES:
						found.append(f"{path.relative_to(REPO_ROOT)}:{n}: {match.group(0).strip()}")
		self.assertEqual(found, [], "Write border-radius as a radius token.")

	def test_the_theme_defines_one_radius(self):
		css = (FRONTEND / "theme" / "ui-tokens.css").read_text(encoding="utf-8")
		declared = re.findall(r"(--(?:ui-)?radius[\w-]*)\s*:\s*([^;/]+?)\s*;", css)
		self.assertEqual(
			declared,
			[("--radius-card", "14px"), ("--radius-control", "10px"), ("--radius-round", "9999px")],
		)

	def test_the_tailwind_radius_names_all_map_to_the_one_value(self):
		tokens = (FRONTEND / "theme" / "tokens.js").read_text(encoding="utf-8")
		block = tokens[tokens.index("export const radius") :].split("};", 1)[0]
		values = set(re.findall(r":\s*([^,\n]+),", block))
		self.assertEqual(values, {'"0"', "card", "control", "uiRadius.round"})


if __name__ == "__main__":
	unittest.main()
