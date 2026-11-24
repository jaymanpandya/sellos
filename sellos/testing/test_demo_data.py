"""The demo's content (sellos/testing/demo_data.py) is realistic and consistent.

Unit tests, no bench: they read the data tables only. The records the data becomes are checked by
sellos/tests/test_demo_environment.py, which seeds a real demo site.
"""

import json
import re
import unittest
from itertools import pairwise

from sellos.testing import demo, demo_data

PAYOUTS = {"due", "approved", "paid", "none"}


def strings(value):
	"""Every string in a nested data structure."""
	if isinstance(value, str):
		yield value
	elif isinstance(value, dict):
		for item in value.values():
			yield from strings(item)
	elif isinstance(value, (list, tuple)):
		for item in value:
			yield from strings(item)


def unit_numbers(spec):
	if "tower" in spec:
		ranges = spec["tower"][2]
		return {str(n) for low, high in ranges for n in range(low, high + 1)}
	return {u[0] for u in spec["units"]}


def carpet_area(spec, number):
	if "tower" in spec:
		return 905 if number in spec["three_bhk"] else spec["tower"][3]
	return next(u[3] for u in spec["units"] if u[0] == number)


class TestDemoData(unittest.TestCase):
	def test_every_company_has_market_data(self):
		self.assertEqual({c["word"] for c in demo.COMPANIES}, set(demo_data.MARKET))

	def test_nothing_looks_like_a_test_fixture(self):
		for word, market in demo_data.MARKET.items():
			for text in strings(market):
				for forbidden in demo_data.FORBIDDEN_WORDS:
					self.assertNotIn(forbidden, text.lower(), f"{word}: {text!r}")

	def test_no_phone_number_is_written_in_the_data(self):
		# Numbers come from sellos.tests.phones (the guard of SOS-P1-06), so no digit run of 10 appears.
		for text in strings(demo_data.MARKET):
			if re.fullmatch(r"[PA]\d{11}", text):
				continue  # a RERA number, not a phone number
			self.assertIsNone(re.search(r"\d{10}", text), text)
			self.assertNotIn("+91", text)

	def test_projects_are_distinct_and_registered(self):
		seen = set()
		for word, market in demo_data.MARKET.items():
			names = [p["name"] for p in market["projects"]]
			self.assertEqual(len(names), len(set(names)), word)
			for project in market["projects"]:
				self.assertRegex(project["rera"], r"^P\d{11}$")
				self.assertNotIn(project["rera"], seen)  # a RERA number is unique to a project
				seen.add(project["rera"])
				self.assertLess(project["developer"], len(market["developers"]))
				self.assertTrue(4_000 <= project["rate"] <= 80_000, project["name"])

	def test_unit_numbers_are_unique_in_a_project(self):
		for market in demo_data.MARKET.values():
			for project in market["projects"]:
				if "units" in project:
					numbers = [u[0] for u in project["units"]]
					self.assertEqual(len(numbers), len(set(numbers)), project["name"])
				else:
					self.assertTrue(set(project["three_bhk"]) <= unit_numbers(project))

	def test_hold_and_block_name_real_units_nobody_else_uses(self):
		for word, market in demo_data.MARKET.items():
			held, blocked = market["hold"], market["block"]
			for ref in (held, blocked):
				spec = market["projects"][ref["project"]]
				self.assertIn(ref["unit"], unit_numbers(spec), word)
			dealt = {
				(d["project"], d["unit"]) for d in market["deals"] if "unit" in d
			}  # a deal's unit is neither held nor blocked
			self.assertNotIn((held["project"], held["unit"]), dealt)
			self.assertNotIn((blocked["project"], blocked["unit"]), dealt)
			self.assertNotEqual((held["project"], held["unit"]), (blocked["project"], blocked["unit"]))
			lead = demo.COMPANIES[[c["word"] for c in demo.COMPANIES].index(word)]["leads"][held["lead"]]
			self.assertEqual(lead[8], 0)  # the hold is made by the lead's own agent, agent 0

	def test_deals_cover_every_stage_and_are_priced_sensibly(self):
		for word, market in demo_data.MARKET.items():
			leads = demo.COMPANIES[[c["word"] for c in demo.COMPANIES].index(word)]["leads"]
			payouts = [d["payout"] for d in market["deals"]]
			self.assertTrue(set(payouts) <= PAYOUTS)
			self.assertEqual({"due", "approved", "paid", "none"}, set(payouts), word)
			self.assertEqual(
				len({d["lead"] for d in market["deals"]}), len(market["deals"])
			)  # a client has one
			for deal in market["deals"]:
				self.assertLess(deal["lead"], len(leads))
				self.assertIn(deal["partner"], (0, 20, 25, 40))
				self.assertEqual(deal["partner"] == 0, deal["payout"] == "none")
				self.assertEqual(deal["approved"], deal["payout"] != "none")
				if "unit" in deal:
					spec = market["projects"][deal["project"]]
					self.assertIn(deal["unit"], unit_numbers(spec))
					per_foot = deal["price"] / carpet_area(spec, deal["unit"])
					self.assertTrue(0.8 * spec["rate"] <= per_foot <= 1.6 * spec["rate"], (word, deal))
				else:
					prop = market["properties"][deal["property"]]
					self.assertEqual(deal["price"], prop["asking_price"])

	def test_the_partner_registers_one_buyer_for_each_decision(self):
		for market in demo_data.MARKET.values():
			decisions = sorted(row[3] for row in market["registrations"])
			self.assertEqual(decisions, ["approve", "reject", "wait"])
			projects = {p["name"] for p in market["projects"]}
			for _name, project, _note, _decision in market["registrations"]:
				self.assertIn(project, projects)
			self.assertEqual(sorted(row[1] for row in market["other_firms"]), ["invited", "pending"])

	def test_sellers_have_a_property_and_a_mandate_of_each_kind(self):
		for market in demo_data.MARKET.values():
			kinds = {s["mandate"][0]: s["mandate"][3] for s in market["sellers"]}
			self.assertEqual(kinds, {"Exclusive": False, "Open": True})  # a Draft and a Signed mandate
			for seller in market["sellers"]:
				self.assertIn(seller["stage"], ("Seller Qualified", "Seller Valuation shared"))

	def test_whatsapp_conversations_show_every_kind(self):
		for word, market in demo_data.MARKET.items():
			customers = market["whatsapp"]["customers"]
			names = [c["name"] for c in customers]
			self.assertEqual(len(names), len(set(names)))
			steps = [kind for c in customers for kind, _ in c["script"]]
			texts = [payload for c in customers for kind, payload in c["script"] if kind == "in"]
			self.assertIn("handoff", steps, word)
			self.assertIn("template", steps, word)
			self.assertIn("STOP", texts, word)  # exactly one customer opts out
			self.assertEqual(texts.count("STOP"), 1)
			self.assertEqual(texts.count("START"), 1)
			for customer in customers:
				self.assertEqual(customer["script"][0][0], "in")  # the customer writes first
			for kind, payload in (s for c in customers for s in c["script"]):
				if kind == "template":
					self.assertEqual(len(payload), 2)  # the template has {{1}} and {{2}}

	def test_phone_seeds_do_not_overlap(self):
		seeds = demo_data.PHONE_SEEDS
		used = {
			"partner": 3 + 3,  # the firm, two other firms and three buyers
			"enquiry": 6,
			"seller": 2,
			"whatsapp": max(len(m["whatsapp"]["customers"]) for m in demo_data.MARKET.values()),
		}
		ranges = sorted((seeds[k], seeds[k] + used[k]) for k in seeds)
		for (_, end), (start, _) in pairwise(ranges):
			self.assertLessEqual(end, start)
		# demo.py's own telephony numbers use seeds 3100 and 3201 to 3204.
		self.assertTrue(all(low > 3300 for low, _ in ranges))

	def test_data_is_plain_json_compatible_apart_from_tuples(self):
		json.dumps(demo_data.MARKET, default=list)


if __name__ == "__main__":
	unittest.main()
