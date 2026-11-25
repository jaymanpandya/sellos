"""SOS-LOOP (demo rebuild, 25 November 2026): the demo names are plain, made up, and drawn without repeats."""

import random
import unittest

from sellos.testing import demo_ctx, demo_data, demo_names


class TestDemoNames(unittest.TestCase):
	"""SOS-LOOP demo rebuild: names by region, no name twice, no label on a name."""

	def test_a_person_is_a_plain_two_word_name(self):
		rng = random.Random(1)
		for region in demo_names.REGIONS:
			for p in demo_names.people(rng, region, 60):
				self.assertEqual(len(p["name"].split()), 2, p["name"])
				for word in (*demo_data.FORBIDDEN_WORDS, "website", "referral", "portal"):
					self.assertNotIn(word, p["name"].lower())

	def test_no_name_is_drawn_twice_when_the_same_used_set_is_passed(self):
		rng, used = random.Random(2), set()
		names = [p["name"] for _ in range(4) for p in demo_names.people(rng, "bom", 60, used)]
		self.assertEqual(len(names), len(set(names)))

	def test_mumbai_has_every_community_and_ahmedabad_is_mainly_gujarati(self):
		bom = demo_names.people(random.Random(3), "bom", 250)
		self.assertEqual({p["community"] for p in bom}, set(demo_names.COMMUNITIES))
		amd = demo_names.people(random.Random(4), "amd", 200)
		self.assertGreater(sum(p["community"] == "gujarati" for p in amd), 0.65 * len(amd))

	def test_the_same_seed_gives_the_same_people(self):
		self.assertEqual(
			demo_names.people(random.Random(5), "amd", 20), demo_names.people(random.Random(5), "amd", 20)
		)

	def test_each_company_has_every_staff_role_and_four_agents(self):
		for word in ("bom", "amd"):
			staff = demo_names.STAFF[word]
			self.assertEqual(len(staff["agents"]), 4)
			for key in ("admin", "manager", "partner", "client"):
				self.assertTrue(staff[key])

	def test_the_context_knows_the_minimums_of_the_brief(self):
		m = demo_ctx.MINIMUMS
		self.assertEqual((m["leads"], m["projects"], m["developers"], m["deals"]), (180, 12, 6, 30))


if __name__ == "__main__":
	unittest.main()
