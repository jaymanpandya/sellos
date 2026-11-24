"""SOS-LOOP (design system pass, 25 November 2026): the token file is the only place a value is written.

docs/DESIGN_SYSTEM.md, section 1. `frontend/src/theme/ui-tokens.js` holds every value of section 2 of the source
document and the five SellOS areas; `ui-tokens.css` repeats them as CSS variables. This test fails when the two
disagree, and when the checking script (scripts/check_design_system.py) stops catching a page that draws its own
button, card, heading, radius, padding, shadow, font size or colour.
"""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
THEME = REPO_ROOT / "frontend" / "src" / "theme"
JS = (THEME / "ui-tokens.js").read_text(encoding="utf-8")
CSS = (THEME / "ui-tokens.css").read_text(encoding="utf-8")

AREAS = ["sales", "calls", "inventory", "money", "company"]


def css_var(name):
	match = re.search(rf"{re.escape(name)}\s*:\s*([^;]+);", CSS)
	return match.group(1).strip() if match else None


def load_checker():
	spec = importlib.util.spec_from_file_location(
		"check_design_system", REPO_ROOT / "scripts" / "check_design_system.py"
	)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class TestDesignTokens(unittest.TestCase):
	"""SOS-LOOP design system pass: the tokens of section 2 and the areas, defined once."""

	def test_every_value_of_section_2_is_in_the_token_file(self):
		for needle in (
			"card: 14, control: 10, round: 9999",
			"touchHeight: 44",
			"cardPadding: { base: 16, from640: 20 }",
			"gapBetweenCards: 16",
			"fieldGap: { across: 20, down: 16 }",
			"pageMargin: { base: 16, from640: 24 }",
			"contentMaxWidth: 1440",
			"fast: 120, base: 180, slow: 250",
			"cubic-bezier(0.16, 1, 0.3, 1)",
			'font: "Inter"',
			"typeFloor: { smallPrint: 14, reading: 16 }",
		):
			self.assertIn(needle, JS)

	def test_the_css_variables_repeat_the_tokens(self):
		self.assertEqual(css_var("--radius-card"), "14px")
		self.assertEqual(css_var("--radius-control"), "10px")
		self.assertEqual(css_var("--ui-card-pad"), "16px")
		self.assertEqual(css_var("--ui-gap-cards"), "16px")
		self.assertEqual(css_var("--ui-field-gap-x"), "20px")
		self.assertEqual(css_var("--ui-field-gap-y"), "16px")
		self.assertEqual(css_var("--ui-page-margin"), "16px")
		self.assertEqual(css_var("--ui-content-max"), "1440px")
		self.assertEqual(
			css_var("--ui-shadow-card"),
			"0 1px 2px rgba(17, 24, 39, 0.04), 0 6px 20px -8px rgba(17, 24, 39, 0.1)",
		)

	def test_each_area_has_one_accent_one_tint_one_ink_and_one_icon(self):
		for key in AREAS:
			block = re.search(rf"\t{key}: \{{(.*?)\n\t\}},", JS, re.S)
			self.assertIsNotNone(block, key)
			for field in ("label", "accent", "soft", "ink", "icon"):
				self.assertIn(f"{field}:", block.group(1), f"{key} has no {field}")
			css = re.search(rf'\[data-area="{key}"\]\s*\{{(.*?)\}}', CSS, re.S)
			self.assertIsNotNone(css, f"{key} has no CSS block")
			for var in ("--area-accent", "--area-soft", "--area-ink"):
				self.assertIn(var, css.group(1))


class TestDesignSystemCheck(unittest.TestCase):
	"""SOS-LOOP design system pass: the checking script catches a page that draws its own look."""

	def findings(self, template):
		checker = load_checker()
		with tempfile.TemporaryDirectory() as folder:
			path = Path(folder) / "Page.vue"
			path.write_text(f"<template>{template}</template>", encoding="utf-8")
			return {rule for _, rule, _ in checker.findings(path)}

	def test_it_catches_every_kind_of_own_drawing(self):
		self.assertIn("own control", self.findings("<button>Go</button>"))
		self.assertIn("own heading", self.findings("<h2>Title</h2>"))
		self.assertIn("radius", self.findings('<div class="rounded-card"></div>'))
		self.assertIn("shadow", self.findings('<div class="shadow-card"></div>'))
		self.assertIn("font size", self.findings('<p class="text-sm"></p>'))
		self.assertIn("padding", self.findings('<div class="p-4"></div>'))
		self.assertIn("colour", self.findings('<p class="text-ink-muted"></p>'))
		self.assertIn("colour", self.findings('<p style="color:#fff"></p>'))
		self.assertIn("own card", self.findings('<div class="ui-card"></div>'))

	def test_it_lets_layout_and_the_named_text_roles_through(self):
		self.assertEqual(
			self.findings(
				'<div class="flex items-center gap-ui-md mb-ui-md min-w-0 truncate"><p class="ui-text-muted"></p></div>'
			),
			set(),
		)

	def test_the_pages_that_pass_are_not_on_the_backlog(self):
		self.assertEqual(load_checker().main([]), 0)


if __name__ == "__main__":
	unittest.main()
