"""The demo inventory content (sellos/testing/demo_inventory.py): volumes, formats, no forbidden word, and the
same content for the same seed. Unit tests, no bench: only the pure generators run."""

import random
import re
import unittest
from datetime import date

from sellos.testing import demo_data, demo_names
from sellos.testing import demo_inventory as inv
from sellos.testing.demo_ctx import MINIMUMS

TODAY = date(2026, 11, 25)
REGIONS = ("bom", "amd")
FORBIDDEN = (*demo_data.FORBIDDEN_WORDS, "regression")


def content(region, seed=1):
	rng = random.Random(seed)
	developers = inv.make_developers(rng, region, set())
	projects = inv.make_projects(rng, region, TODAY, developers)
	properties = inv.make_properties(rng, region, TODAY)
	plan = inv.plan_listings(rng, projects, properties)
	return developers, projects, properties, plan


def strings(value):
	if isinstance(value, str):
		yield value
	elif isinstance(value, dict):
		for item in value.values():
			yield from strings(item)
	elif isinstance(value, (list, tuple)):
		for item in value:
			yield from strings(item)


class TestDemoInventory(unittest.TestCase):
	def test_volumes(self):
		for region in REGIONS:
			developers, projects, properties, plan = content(region)
			self.assertGreaterEqual(len(developers), MINIMUMS["developers"])
			self.assertGreaterEqual(len(projects), MINIMUMS["projects"])
			units = [len(inv.project_units(p)) for p in projects]
			self.assertGreaterEqual(min(units), 60)
			self.assertGreaterEqual(sum(units) / len(units), MINIMUMS["units_per_project"])
			self.assertGreaterEqual(len(properties), MINIMUMS["properties"])
			localities = {p["locality"] for p in projects} | {p["locality"] for p in properties}
			self.assertEqual(len(localities), MINIMUMS["localities"])
			self.assertEqual(len({p["locality"] for p in properties}), MINIMUMS["localities"])
			self.assertEqual(len(plan["primary"]), 18)
			self.assertGreaterEqual(len(plan["direct"]), 20)
			self.assertGreaterEqual(len(plan["partner"]), 4)

	def test_localities_are_the_regions(self):
		for region in REGIONS:
			_, projects, properties, _ = content(region)
			names = {name for name, _, _ in inv.LOCALITIES[region]}
			self.assertEqual(len(names), 10)
			self.assertLessEqual({p["locality"] for p in projects + properties}, names)

	def test_names_are_unique_and_projects_linked(self):
		for region in REGIONS:
			developers, projects, properties, _ = content(region)
			names = [d["developer_name"] for d in developers]
			self.assertEqual(len(set(names)), len(names))
			self.assertEqual(len({p["project_name"] for p in projects}), len(projects))
			self.assertEqual(len({p["title"] for p in properties}), len(properties))
			self.assertEqual(len({p["rera_number"] for p in projects}), len(projects))
			for project in projects:
				self.assertIn(project["developer_name"], names)
				self.assertIn(project["project_status"], ("Under construction", "Ready to move"))
				self.assertTrue(project["possession_date"])
				self.assertGreaterEqual(len(project["amenities"]), 6)
			self.assertEqual(
				{d["developer_name"] for d in developers}, {p["developer_name"] for p in projects}
			)

	def test_rera_formats(self):
		_, bom, bom_props, _ = content("bom")
		_, amd, amd_props, _ = content("amd")
		for p in bom:
			self.assertRegex(p["rera_number"], r"^P518000\d{5}$")
		for p in bom_props:
			self.assertTrue(not p["rera_number"] or re.match(r"^P518000\d{5}$", p["rera_number"]))
		for p in amd:
			self.assertRegex(p["rera_number"], r"^PR/GJ/AHMEDABAD/[A-Z0-9/]+$")
			self.assertLessEqual(len(p["rera_number"]), 40)
		for p in amd_props:
			self.assertLessEqual(len(p["rera_number"]), 40)

	def test_units_and_prices(self):
		for region in REGIONS:
			_, projects, _, _ = content(region)
			configs = set()
			for project in projects:
				units = inv.project_units(project)
				numbers = {(u["tower_name"], u["unit_number"]) for u in units}
				self.assertEqual(len(numbers), len(units))
				self.assertGreaterEqual(len({u["configuration"] for u in units}), 2)
				low, high = {"bom": (12000, 70000), "amd": (4000, 9500)}[region]
				self.assertTrue(low <= project["rate"] <= high, project["rate"])
				for unit in units:
					configs.add(unit["configuration"])
					self.assertEqual(unit["price"], int(project["rate"] * unit["carpet_area"]))
					self.assertGreater(unit["carpet_area"], 300)
				self.assertTrue(set(inv.tower_floor_groups(project["towers"][0], 1)))
			self.assertEqual(configs, {"1 BHK", "2 BHK", "3 BHK", "4 BHK"})

	def test_floor_groups_cover_the_unit_numbers(self):
		_, projects, _, _ = content("bom")
		for project in projects:
			for tower in project["towers"]:
				made = []
				for floor in range(1, tower["floors"] + 1):
					for pattern, _, _, _, prefix in inv.tower_floor_groups(tower, floor):
						low, high = (int(x) for x in pattern.split(" to "))
						made += [f"{prefix}{n}" for n in range(low, high + 1)]
				expected = [
					u["unit_number"]
					for u in inv.project_units(project)
					if u["tower_name"] == tower["tower_name"]
				]
				self.assertEqual(made, expected)

	def test_price_lists_and_plans_can_make_a_cost_sheet(self):
		for region in REGIONS:
			_, projects, _, _ = content(region)
			for project in projects:
				pl = project["price_list"]
				self.assertLessEqual(date.fromisoformat(pl["effective_from"]), TODAY)
				self.assertEqual(pl["base_rate"], project["rate"])
				self.assertTrue(all(c["value"] > 0 for c in pl["charges"]))
				plan = project["payment_plan"]
				self.assertEqual(sum(i["percent"] for i in plan["instalments"]), 100)
				if plan["plan_type"] == "Construction linked":
					self.assertTrue(all(i["due_on"] for i in plan["instalments"]))

	def test_properties_are_believable(self):
		for region in REGIONS:
			_, _, properties, plan = content(region)
			for p in properties:
				self.assertGreater(p["asking_price"], 1_000_000)
				self.assertTrue(2 <= p["age_years"] <= 28)
				self.assertTrue(p["building_name"] and p["configuration"] and p["carpet_area"] > 0)
			listed = plan["direct"] + plan["partner"]
			self.assertEqual(len(set(listed)), len(listed))
			self.assertGreaterEqual(len(properties) - len(listed), 6)

	def test_no_forbidden_word(self):
		for region in REGIONS:
			for part in content(region):
				for text in strings(part):
					self.assertFalse(any(w in f"{text.lower()} " for w in FORBIDDEN), text)
			_, projects, properties, _ = content(region)
			for project in projects:
				_title, description, _ = inv.primary_listing(
					project, {**inv.project_units(project)[0], "floor": 3}
				)
				self.assertFalse(any(w in f"{description.lower()} " for w in FORBIDDEN))
			for prop in properties:
				self.assertFalse(any(w in f"{inv.property_listing(prop)[1].lower()} " for w in FORBIDDEN))

	def test_same_seed_same_content(self):
		for region in REGIONS:
			self.assertEqual(content(region, 7), content(region, 7))

	def test_contact_persons_are_made_up_people(self):
		used = set()
		developers = inv.make_developers(random.Random(3), "bom", used)
		for dev in developers:
			self.assertIn(dev["contact_person"], used)
			self.assertTrue(dev["email"].endswith(".example.com"))
		self.assertEqual(set(demo_names.REGIONS), set(REGIONS))


if __name__ == "__main__":
	unittest.main()
