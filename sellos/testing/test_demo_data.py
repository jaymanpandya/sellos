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


class TestSeedFailsLoudly(unittest.TestCase):
	"""A failed seed step is named with its error and fails the seed; it is never only a missing section."""

	def test_a_result_with_no_failed_step_has_no_failures(self):
		line = json.dumps({"site": "s", "leads": 3, "failed_steps": []})
		self.assertEqual(demo.failed_steps_of("s", line), [])

	def test_each_failed_step_is_named_with_its_error(self):
		failed = [
			{"step": "partners", "error": "TypeError: bad seed"},
			{"step": "whatsapp", "error": "ValidationError: no template"},
		]
		line = json.dumps({"site": "s", "failed_steps": failed})
		self.assertEqual(
			demo.failed_steps_of("s", line),
			[("s", "partners", "TypeError: bad seed"), ("s", "whatsapp", "ValidationError: no template")],
		)

	def test_a_line_that_is_not_the_result_counts_as_a_failure(self):
		for line in ("seeded", "", '{"site": "s"}', "[1, 2]"):
			found = demo.failed_steps_of("s", line)
			self.assertEqual(len(found), 1, line)
			self.assertIn("not understood", found[0][2])

	def test_a_failing_step_is_rolled_back_recorded_and_the_next_step_still_runs(self):
		from unittest import mock

		import frappe

		del demo.STEP_FAILURES[:]
		self.addCleanup(demo.STEP_FAILURES.clear)
		db = mock.MagicMock()

		def broken():
			raise ValueError("no such project")

		with (
			mock.patch.object(frappe, "db", db),
			mock.patch.object(demo.sys, "stderr", mock.MagicMock()),
		):
			self.assertIsNone(demo._isolated("deals", broken))
			self.assertEqual(demo._isolated("visits", lambda: "made"), "made")
		db.rollback.assert_called_once()
		self.assertEqual(demo.STEP_FAILURES, [{"step": "deals", "error": "ValueError: no such project"}])

	def test_seed_raises_naming_every_failed_site_and_step(self):
		from unittest import mock

		results = {
			"sellos_tenant_demoalpha.localhost": json.dumps({"failed_steps": []}),
			"sellos_tenant_demobeta.localhost": json.dumps(
				{"failed_steps": [{"step": "deals and commission", "error": "KeyError: 'rate'"}]}
			),
		}
		with (
			mock.patch.object(demo, "ensure_control"),
			mock.patch.object(demo, "provision_companies"),
			mock.patch.object(demo, "_run_on", side_effect=lambda site, *a, **k: results[site]),
			mock.patch("builtins.print"),
		):
			with self.assertRaises(demo.DemoSeedFailed) as caught:
				demo.seed()
			self.assertEqual(demo.main(["seed"]), 1)
		message = str(caught.exception)
		self.assertIn("sellos_tenant_demobeta.localhost", message)
		self.assertIn("deals and commission", message)
		self.assertIn("KeyError: 'rate'", message)
		self.assertNotIn("demoalpha", message)


if __name__ == "__main__":
	unittest.main()
