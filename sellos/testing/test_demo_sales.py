"""The demo's sales content (sellos/testing/demo_sales.py): volumes, formats, no test words, same output twice.

Plain unit tests with no bench: they read the pure generator functions only. The records the builder makes
are checked by seeding a demo site.
"""

import random
import unittest
from collections import Counter
from datetime import date

from sellos.testing import demo_ctx, demo_data, demo_names, demo_sales

TODAY = date(2026, 11, 25)
FORBIDDEN = (*demo_data.FORBIDDEN_WORDS, "regression")


def strings(value):
	if isinstance(value, str):
		yield value
	elif isinstance(value, dict):
		for item in value.values():
			yield from strings(item)
	elif isinstance(value, (list, tuple)):
		for item in value:
			yield from strings(item)


def everything(word):
	"""All the plans of one company, drawn in the order build() draws them."""
	rng = random.Random(demo_ctx.SEED_OF[word])
	used = set()
	staff = demo_names.STAFF[word]
	firms = demo_sales.firm_plan(rng, word, TODAY, used, staff["partner"])
	approved = sum(1 for f in firms if f["status"] == "approved")
	registrations = demo_sales.registration_plan(rng, word, TODAY, used, approved)
	sellers = demo_sales.seller_plan(rng, word, TODAY, used)
	client = demo_sales.client_seller_spec(rng, word, staff["client"], "client@example.com")
	deals = demo_sales.deal_plan(rng, TODAY)
	return {
		"firms": firms,
		"registrations": registrations,
		"sellers": sellers,
		"client": client,
		"deals": deals,
		"used": used,
	}


class TestDemoSales(unittest.TestCase):
	def test_the_volumes_meet_the_minimums(self):
		for word in ("bom", "amd"):
			plans = everything(word)
			self.assertGreaterEqual(len(plans["sellers"]), demo_ctx.MINIMUMS["sellers"])
			self.assertGreaterEqual(len(plans["sellers"]), demo_ctx.MINIMUMS["mandates"])
			self.assertGreaterEqual(len(plans["firms"]), demo_ctx.MINIMUMS["partners"])
			self.assertGreaterEqual(len(plans["deals"]), demo_ctx.MINIMUMS["deals"])
			payouts = Counter(d["payout"] for d in plans["deals"] if d["payout"])
			self.assertGreaterEqual(sum(payouts.values()), demo_ctx.MINIMUMS["payouts"])

	def test_every_mandate_state_and_seller_stage_is_there(self):
		sellers = everything("bom")["sellers"]
		self.assertEqual({s["mandate"]["state"] for s in sellers}, set(demo_sales.MANDATE_STATES))
		stages = {name for name, _state in demo_sales.SELLER_PLAN}
		self.assertEqual({s["stage"] for s in sellers}, stages)
		self.assertEqual(len(stages), 10)

	def test_a_running_mandate_has_not_run_out_and_an_expired_one_has(self):
		for seller in everything("amd")["sellers"]:
			mandate = seller["mandate"]
			days = mandate["term_months"] * 30
			if mandate["state"] == "signed":
				self.assertLess(mandate["start_days_ago"], days)
			if mandate["state"] == "expired":
				self.assertGreater(mandate["start_days_ago"], days + 30)

	def test_the_sellers_properties_and_names_are_all_different(self):
		for word in ("bom", "amd"):
			plans = everything(word)
			titles = [s["property"]["title"] for s in plans["sellers"]] + [
				plans["client"]["property"]["title"]
			]
			self.assertEqual(len(titles), len(set(titles)))
			emails = [s["email"] for s in plans["sellers"]]
			self.assertEqual(len(emails), len(set(emails)))
			seeds = [s["phone_seed"] for s in plans["sellers"]]
			self.assertEqual(len(seeds), len(set(seeds)))
			for seller in plans["sellers"]:
				self.assertTrue(seller["email"].endswith("@example.com"))
				self.assertEqual(seller["name"], " ".join(seller["name"].split()))

	def test_the_client_signs_in_to_a_listed_seller_with_enquiries(self):
		client = everything("bom")["client"]
		self.assertEqual(client["stage"], "Listed")
		self.assertEqual(client["mandate"]["state"], "signed")
		self.assertGreaterEqual(client["enquiries"], 3)
		self.assertEqual(client["name"], demo_names.STAFF["bom"]["client"])

	def test_firms_cover_every_status_and_the_first_is_the_demo_partner(self):
		for word in ("bom", "amd"):
			firms = everything(word)["firms"]
			self.assertEqual({f["status"] for f in firms}, {"approved", "pending", "invited", "suspended"})
			self.assertEqual(firms[0]["status"], "approved")
			self.assertEqual(firms[0]["contact_person"], demo_names.STAFF[word]["partner"])
			names = [f["firm_name"] for f in firms]
			self.assertEqual(len(names), len(set(names)))

	def test_rera_and_pan_formats(self):
		for word, pattern in (("bom", demo_sales.MAHA_RERA_RE), ("amd", demo_sales.GUJARAT_RERA_RE)):
			firms = everything(word)["firms"]
			for firm in firms:
				self.assertRegex(firm["rera_number"], pattern)
				self.assertRegex(firm["pan"], demo_sales.PAN_RE)
			self.assertEqual(len({f["rera_number"] for f in firms}), len(firms))

	def test_registrations_cover_all_six_statuses_for_approved_firms(self):
		for word in ("bom", "amd"):
			plans = everything(word)
			approved = sum(1 for f in plans["firms"] if f["status"] == "approved")
			registrations = plans["registrations"]
			self.assertEqual(
				{r["status"] for r in registrations},
				{"Registered", "Approved", "Visited", "Booked", "Expired", "Rejected"},
			)
			self.assertTrue(all(r["firm_index"] < approved for r in registrations))
			self.assertTrue(all(r["rejection"] for r in registrations if r["status"] == "Rejected"))
			seeds = [r["phone_seed"] for r in registrations]
			self.assertEqual(len(seeds), len(set(seeds)))

	def test_names_are_never_repeated_across_a_company(self):
		for word in ("bom", "amd"):
			plans = everything(word)
			names = (
				[f["contact_person"] for f in plans["firms"]]
				+ [r["buyer_name"] for r in plans["registrations"]]
				+ [s["name"] for s in plans["sellers"]]
			)
			self.assertEqual(len(names), len(set(names)))

	def test_payouts_have_at_least_four_in_each_status(self):
		deals = everything("bom")["deals"]
		counts = Counter(d["payout"] for d in deals if d["payout"])
		self.assertEqual(set(counts), {"due", "approved", "paid", "hold"})
		self.assertTrue(all(n >= 4 for n in counts.values()))

	def test_every_deal_kind_is_planned_and_the_splits_add_to_100(self):
		deals = everything("amd")["deals"]
		kinds = {d["kind"] for d in deals}
		self.assertEqual(
			kinds, {"partner_unit", "property_approved", "property_pending", "booked", "cancelled"}
		)
		for deal in deals:
			agent, partner, company = demo_sales.split_percents(
				(deal["partner_percent"], deal["company_percent"])
			)
			self.assertEqual(agent + partner + company, 100)
			self.assertGreater(agent, 0)
			if deal["kind"] == "partner_unit":
				self.assertGreater(partner, 0)

	def test_a_paid_deal_is_old_enough_to_have_been_paid(self):
		for deal in everything("bom")["deals"]:
			if deal["payout"] == "paid":
				self.assertGreaterEqual(deal["days_ago"], 25)

	def test_prices_round_to_ten_thousand(self):
		self.assertEqual(demo_sales.round_price(12345678), 12350000)
		self.assertEqual(demo_sales.round_price(69500000 * 0.97) % 10000, 0)

	def test_no_test_words_anywhere(self):
		for word in ("bom", "amd"):
			for text in strings(everything(word)):
				lowered = text.lower()
				for forbidden in FORBIDDEN:
					self.assertNotIn(forbidden, lowered, text)
		for title, note in demo_sales.DOSSIER_NOTES:
			for forbidden in FORBIDDEN:
				self.assertNotIn(forbidden, f"{title} {note}".lower())

	def test_the_same_seed_gives_the_same_plans(self):
		for word in ("bom", "amd"):
			self.assertEqual(everything(word), everything(word))

	def test_the_two_companies_differ(self):
		self.assertNotEqual(everything("bom")["sellers"], everything("amd")["sellers"])

	def test_localities_belong_to_the_region(self):
		for word in ("bom", "amd"):
			for seller in everything(word)["sellers"]:
				self.assertIn(seller["property"]["locality"], demo_sales.LOCALITIES[word])
				self.assertEqual(seller["city"], demo_names.REGIONS[word]["city"])


if __name__ == "__main__":
	unittest.main()
