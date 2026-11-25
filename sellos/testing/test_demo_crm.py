"""Unit tests of the pure generators of the demo CRM (no bench): volumes, formats, words and determinism."""

import random
import unittest
from collections import Counter
from datetime import date

from sellos.testing import demo_crm, demo_ctx, demo_data

TODAY = date(2026, 11, 25)
AGENTS = ["a1@example.com", "a2@example.com", "a3@example.com", "a4@example.com"]
PROJECTS = {
	"bom": [
		{"name": f"Harbour View {i}", "locality": loc} for i, loc in enumerate(demo_crm.LOCALITIES["bom"])
	],
	"amd": [
		{"name": f"Sabarmati Court {i}", "locality": loc} for i, loc in enumerate(demo_crm.LOCALITIES["amd"])
	],
}
SOURCES = (
	"Website",
	"Referral",
	"Hoarding campaign",
	"Walk in",
	"Property portal",
	"Instagram",
	"Channel partner",
)


def leads_of(region):
	rng = random.Random(demo_ctx.SEED_OF[region])
	return demo_crm.generate_leads(rng, region, TODAY, PROJECTS[region], AGENTS)


def strings(value):
	if isinstance(value, str):
		yield value
	elif isinstance(value, dict):
		for item in value.values():
			yield from strings(item)
	elif isinstance(value, (list, tuple)):
		for item in value:
			yield from strings(item)


class TestDemoCrm(unittest.TestCase):
	def test_volumes_of_both_companies(self):
		minimums = demo_ctx.MINIMUMS
		for region in ("bom", "amd"):
			leads = leads_of(region)
			self.assertGreaterEqual(len(leads), minimums["leads"])
			stages = Counter(lead["stage"] for lead in leads)
			self.assertEqual(set(stages), set(demo_crm.STAGES))
			self.assertGreaterEqual(min(stages.values()), minimums["leads_per_stage"])
			consent = Counter(lead["consent"] for lead in leads)
			unknown = consent["unknown"] + consent["expired"]
			for count in (consent["consented"], unknown, consent["optedout"], consent["dnd"]):
				self.assertGreaterEqual(count, minimums["leads_per_consent_state"])
			self.assertGreaterEqual(demo_crm.count_activities(leads), minimums["activities"])
			self.assertGreaterEqual(sum(len(lead["calls"]) for lead in leads), minimums["call_logs"] + 5)
			self.assertGreaterEqual(sum(len(lead["visits"]) for lead in leads), minimums["site_visits"])

	def test_sources_agents_and_people(self):
		for region in ("bom", "amd"):
			leads = leads_of(region)
			sources = {lead["source"] for lead in leads}
			for wanted in SOURCES:
				self.assertIn(wanted, sources)
			self.assertEqual({lead["agent"] for lead in leads if lead["agent"]}, set(AGENTS))
			unassigned = [lead for lead in leads if not lead["agent"]]
			self.assertGreaterEqual(len(unassigned), 5)
			self.assertTrue(all(lead["stage"] == "New" for lead in unassigned))
			names = [lead["name"] for lead in leads]
			self.assertEqual(len(names), len(set(names)))
			for lead in leads:
				self.assertRegex(lead["name"], r"^[A-Z][a-z]+ [A-Z][a-z]+$")
				self.assertNotIn(lead["source"].lower(), lead["name"].lower())
			self.assertGreaterEqual(sum(1 for lead in leads if lead["client_type"] == "NRI"), 8)
			self.assertTrue(any(lead["email"] is None for lead in leads))
			self.assertEqual(leads[40]["phone_seed"], leads[41]["phone_seed"])
			self.assertEqual(len({lead["phone_seed"] for lead in leads}), len(leads) - 1)

	def test_dates_never_in_the_future(self):
		for region in ("bom", "amd"):
			for lead in leads_of(region):
				age = lead["age_days"]
				self.assertTrue(0 <= age <= 90)
				days = [m["day"] for m in lead["moves"]]
				self.assertEqual(days, sorted(days))
				self.assertLessEqual(days[-1], max(age, 0.2))
				for item in (*lead["calls"], *lead["notes_log"]):
					self.assertLessEqual(item["day"], max(age, 0.2))
				for visit in lead["visits"]:
					if visit["days_ago"] > 0:
						self.assertLessEqual(visit["days_ago"], max(age - 2, 1))
					self.assertTrue(-14 <= visit["days_ago"] <= 21)

	def test_site_visits_cover_every_status_and_tomorrow(self):
		for region in ("bom", "amd"):
			visits = [v for lead in leads_of(region) for v in lead["visits"]]
			self.assertEqual({v["status"] for v in visits}, {"Scheduled", "Done", "Cancelled"})
			tomorrow = [v for v in visits if v["days_ago"] == -1 and v["confirmation"] == "Not confirmed"]
			self.assertGreaterEqual(len(tomorrow), 4)
			self.assertIn("Did not come", {v["outcome"] for v in visits})
			self.assertIn("Rescheduled", {v["confirmation"] for v in visits})
			self.assertIn("Confirmed", {v["confirmation"] for v in visits})

	def test_follow_ups_overdue_today_and_later(self):
		for region in ("bom", "amd"):
			kinds = Counter(lead["follow_up"]["kind"] for lead in leads_of(region) if lead["follow_up"])
			self.assertTrue(all(kinds[k] for k in ("overdue", "today", "later")))

	def test_formats_and_forbidden_words(self):
		for region in ("bom", "amd"):
			leads = leads_of(region)
			for lead in leads:
				if lead["email"]:
					self.assertTrue(lead["email"].endswith("@example.com"))
				self.assertLessEqual(lead["budget_from"], lead["budget_to"])
				self.assertEqual(lead["budget_to"] % 100_000, 0)
				for configuration in lead["configuration"]:
					self.assertIn(configuration, ("1 RK", "1 BHK", "2 BHK", "3 BHK", "4 BHK and above"))
			for text in strings(leads):
				self.assertNotRegex(text, r"\d{10}")
				for forbidden in (*demo_data.FORBIDDEN_WORDS, "regression"):
					self.assertNotIn(forbidden, text.lower() + " ")

	def test_money_text(self):
		self.assertEqual(demo_crm.money_text(8_500_000), "85 lakh")
		self.assertEqual(demo_crm.money_text(14_000_000), "1.4 crore")

	def test_same_seed_same_leads(self):
		self.assertEqual(leads_of("bom"), leads_of("bom"))
		self.assertNotEqual(leads_of("bom"), leads_of("amd"))


if __name__ == "__main__":
	unittest.main()
