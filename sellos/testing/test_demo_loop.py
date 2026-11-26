"""The demo content of the Leads and Sales round (sellos/testing/demo_loop.py): the plans are pure, so they are
tested without a bench. The records the builder makes are checked by seeding a demo site (sellos.tests
.test_demo_environment)."""

import io
import unittest
from datetime import date, timedelta

from PIL import Image

from sellos.inventory import branding
from sellos.inventory.base import clean_rera_number
from sellos.testing import demo_loop


def periods(today):
	week = today - timedelta(days=today.weekday())
	return {
		"day": (today, today),
		"week": (week, today),
		"month": (today.replace(day=1), today),
		"year": (today.replace(month=1, day=1), today),
	}


class TestSplitDeals(unittest.TestCase):
	DAYS = (
		date(2026, 11, 25),  # a Wednesday
		date(2026, 11, 23),  # a Monday: the week and the day are the same
		date(2026, 11, 1),  # the first of the month
		date(2026, 1, 1),  # the first of the year
		date(2026, 1, 20),
		date(2026, 12, 31),
	)

	def test_every_period_holds_a_deal_and_nothing_is_in_the_future(self):
		for today in self.DAYS:
			rows = demo_loop.deal_plan(today)
			for key, (start, end) in periods(today).items():
				self.assertTrue(any(start <= r["date"] <= end for r in rows), f"{today}: nothing in {key}")
			self.assertTrue(all(r["date"] <= today for r in rows), today)
			self.assertTrue(
				any(r["date"].year == today.year - 1 for r in rows), f"{today}: none outside the year"
			)

	def test_one_two_and_three_partner_splits_all_appear_and_add_to_100(self):
		for today in self.DAYS:
			rows = demo_loop.deal_plan(today)
			self.assertEqual({r["partners"] for r in rows}, {1, 2, 3}, today)
			for r in rows:
				self.assertEqual(len(r["shares"]), r["partners"])
				self.assertEqual(r["agent"] + sum(r["shares"]) + r["company"], 100)
				self.assertGreater(r["price"], 0)

	def test_today_gets_one_of_each(self):
		today = date(2026, 11, 25)
		counts = sorted(r["partners"] for r in demo_loop.deal_plan(today) if r["date"] == today)
		self.assertEqual(counts, [1, 2, 3])

	def test_the_plan_is_the_same_twice(self):
		self.assertEqual(demo_loop.deal_plan(date(2026, 11, 25)), demo_loop.deal_plan(date(2026, 11, 25)))


class TestBranding(unittest.TestCase):
	def test_each_company_has_its_own_readable_colours_and_valid_rera_number(self):
		seen = set()
		for word, spec in demo_loop.PROFILES.items():
			self.assertGreaterEqual(
				branding.contrast_with_white(spec["brand_color"]), branding.MIN_PRIMARY_CONTRAST, word
			)
			self.assertGreaterEqual(
				branding.contrast_with_white(spec["accent_color"]), branding.MIN_ACCENT_CONTRAST, word
			)
			self.assertTrue(clean_rera_number(spec["rera_number"]), word)
			seen.add((spec["brand_color"], spec["accent_color"]))
		self.assertEqual(len(seen), len(demo_loop.PROFILES), "the two companies share a colour scheme")

	def test_the_logos_are_real_different_pngs(self):
		logos = {}
		for word, spec in demo_loop.PROFILES.items():
			png = demo_loop.logo_png(spec["logo"])
			image = Image.open(io.BytesIO(png))
			self.assertEqual((image.format, image.size), ("PNG", (240, 240)))
			self.assertLess(len(png), branding.LOGO_LIMIT)
			logos[word] = png
		self.assertEqual(len(set(logos.values())), len(logos))

	def test_the_note_photos_are_png_pictures_that_differ(self):
		pictures = {demo_loop.photo_png(seed) for seed in range(4)}
		self.assertEqual(len(pictures), 4)
		for p in pictures:
			self.assertEqual(Image.open(io.BytesIO(p)).format, "PNG")


class TestNotePlan(unittest.TestCase):
	def test_every_note_type_is_planned_once_in_the_list_the_company_starts_with(self):
		from sellos.crm import notes

		self.assertEqual([row[0] for row in demo_loop.NOTE_PLAN], list(notes.DEFAULT_TYPES))

	def test_photos_and_inspections_carry_pictures_and_text_is_plain(self):
		by_type = {row[0]: row for row in demo_loop.NOTE_PLAN}
		self.assertGreater(by_type["Photos"][2], 0)
		self.assertGreater(by_type["Inspection"][2], 0)
		for _label, text, _photos, days in demo_loop.NOTE_PLAN:
			self.assertTrue(text and days >= 0)
			self.assertNotRegex(text.lower(), r"\btest\b|\bdummy\b|\bfake\b")
