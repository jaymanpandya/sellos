"""SOS-P7-05: towers, wings and floors of a project, the units of a floor made from a pattern, and a
project's possession date, amenities and brochures."""

from pathlib import Path

import frappe

from sellos.inventory import api, structure
from sellos.inventory.test_p4_01_inventory import InventoryCase, _as
from sellos.tests.files import tiny_pdf_base64


class StructureCase(InventoryCase):
	def setUp(self):
		super().setUp()
		self.project = self.make_project("P705 Tower Project", rera="P51800070501")
		self.tower = structure.add_tower(self.project, "Tower A", "1 to 3")["name"]

	def generate(self, pattern="1201 to 1208", floor=12, **extra):
		args = {"tower": self.tower, "floor": floor, "pattern": pattern, "carpet_area": 640}
		return structure.generate_floor_units(**{**args, **extra})

	def numbers(self, tower=None):
		return sorted(
			frappe.get_all("Unit", filters={"tower": tower or self.tower, "archived": 0}, pluck="unit_number")
		)


class TestTowersAndFloors(StructureCase):
	"""SOS-P7-05: a tower has floors, and an editor adds them."""

	def test_a_tower_is_added_with_its_floors_and_read_back(self):
		doc = frappe.get_doc("Project Tower", self.tower)
		self.assertEqual((doc.project, doc.tower_name), (self.project, "Tower A"))
		self.assertEqual([row.floor_number for row in doc.floors], [1, 2, 3])
		state = api.get_project(self.project)
		self.assertEqual([t["tower_name"] for t in state["towers"]], ["Tower A"])
		self.assertEqual([f["floor_number"] for f in state["towers"][0]["floors"]], [1, 2, 3])

	def test_add_floors_keeps_the_floors_it_has(self):
		structure.add_floors(self.tower, "2 to 5")
		doc = frappe.get_doc("Project Tower", self.tower)
		self.assertEqual([row.floor_number for row in doc.floors], [1, 2, 3, 4, 5])

	def test_a_tower_name_is_unique_in_a_project_but_not_across_projects(self):
		with self.assertRaises(frappe.ValidationError):
			structure.add_tower(self.project, " tower a".title())
		other = self.make_project("P705 Other Project", rera="P51800070502")
		structure.add_tower(other, "Tower A")

	def test_a_bad_floor_range_is_refused(self):
		for floors in ("x", "5 to 1", "1 to 900"):
			with self.subTest(floors=floors), self.assertRaises(frappe.ValidationError):
				structure.add_floors(self.tower, floors)

	def test_a_sales_manager_reads_the_structure_and_can_not_change_it(self):
		_as("sales_manager")
		self.assertEqual(len(api.get_project(self.project)["towers"]), 1)
		with self.assertRaises(frappe.PermissionError):
			structure.add_tower(self.project, "Tower B")


class TestPatternGeneration(StructureCase):
	"""SOS-P7-05: the units of a floor are made from a pattern, again changes nothing, and numbers are unique
	within a tower."""

	def test_a_floor_is_generated_from_a_pattern_with_configuration_and_area(self):
		structure.add_floors(self.tower, "12")
		result = self.generate(configuration="2 BHK", parking=1)
		self.assertEqual(len(result["created"]), 8)
		self.assertEqual(self.numbers(), [str(n) for n in range(1201, 1209)])
		unit = frappe.get_doc("Unit", {"tower": self.tower, "unit_number": "1203"})
		self.assertEqual(
			(unit.floor, unit.configuration, unit.carpet_area, unit.parking, unit.status, unit.project),
			(12, "2 BHK", 640, 1, "Available", self.project),
		)

	def test_the_pattern_run_twice_changes_nothing_that_exists(self):
		self.generate(floor=1, pattern="101 to 104", configuration="1 BHK")
		first = {
			name: frappe.get_doc("Unit", name).modified
			for name in frappe.get_all("Unit", filters={"tower": self.tower}, pluck="name")
		}
		again = self.generate(floor=1, pattern="101 to 106", configuration="3 BHK", carpet_area=999)
		self.assertEqual(again["skipped"], ["101", "102", "103", "104"])
		self.assertEqual(again["created"], ["105", "106"])
		for name, modified in first.items():
			doc = frappe.get_doc("Unit", name)
			self.assertEqual((doc.modified, doc.configuration, doc.carpet_area), (modified, "1 BHK", 640))
		self.assertEqual(len(self.numbers()), 6)
		third = self.generate(floor=1, pattern="101 to 106")
		self.assertEqual((third["created"], len(third["skipped"])), ([], 6))

	def test_unit_numbers_are_unique_within_a_tower_but_not_across_towers(self):
		self.generate(floor=1, pattern="101 to 102")
		with self.assertRaises(frappe.ValidationError):
			self.make_unit(self.project, "101", tower=self.tower)
		other = structure.add_tower(self.project, "Tower B", "1")["name"]
		structure.generate_floor_units(other, 1, "101 to 102", 500)
		self.assertEqual(self.numbers(other), ["101", "102"])

	def test_a_floor_that_is_not_in_the_tower_and_bad_input_are_refused(self):
		for args in (
			{"floor": 9},
			{"pattern": "1208 to 1201", "floor": 1},
			{"pattern": "twelve", "floor": 1},
			{"pattern": "1 to 500", "floor": 1},
			{"carpet_area": 0, "floor": 1},
			{"configuration": "Castle", "floor": 1},
		):
			with self.subTest(args=args), self.assertRaises(frappe.ValidationError):
				self.generate(**{"pattern": "101 to 102", **args})
		self.assertEqual(self.numbers(), [])

	def test_a_prefix_and_leading_zeros_are_kept(self):
		result = self.generate(floor=1, pattern="0101 to 0103", prefix="A-")
		self.assertEqual(result["created"], ["A-0101", "A-0102", "A-0103"])

	def test_an_agent_may_generate_and_a_client_may_not(self):
		_as("agent")
		self.generate(floor=1, pattern="101 to 102")
		_as("client")
		with self.assertRaises(frappe.PermissionError):
			self.generate(floor=1, pattern="103 to 104")


class TestRemoval(StructureCase):
	"""SOS-P7-05: removing a tower or floor with a unit in any status but Available is refused, with the count."""

	def setUp(self):
		super().setUp()
		self.generate(floor=1, pattern="101 to 104")
		self.generate(floor=2, pattern="201 to 202")
		for number, status in (("101", "Held"), ("102", "Sold")):
			doc = frappe.get_doc("Unit", {"tower": self.tower, "unit_number": number})
			api.set_inventory_status("Unit", doc.name, status)

	def test_a_floor_with_held_or_sold_units_is_refused_with_the_count(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			structure.remove_floor(self.tower, 1)
		self.assertIn("2 of its units are not Available", str(caught.exception))
		doc = frappe.get_doc("Project Tower", self.tower)
		self.assertIn(1, [row.floor_number for row in doc.floors])
		self.assertEqual(len(self.numbers()), 6)

	def test_a_tower_with_held_or_sold_units_is_refused_with_the_count(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			structure.remove_tower(self.tower)
		self.assertIn("2 of its units are not Available", str(caught.exception))
		self.assertEqual(frappe.db.get_value("Project Tower", self.tower, "archived"), 0)

	def test_a_floor_of_available_units_is_removed_and_its_units_archived(self):
		structure.remove_floor(self.tower, 2)
		doc = frappe.get_doc("Project Tower", self.tower)
		self.assertEqual([row.floor_number for row in doc.floors], [1, 3])
		self.assertEqual(self.numbers(), ["101", "102", "103", "104"])
		self.assertEqual(frappe.db.count("Unit", {"tower": self.tower, "floor": 2, "archived": 1}), 2)

	def test_a_tower_is_removed_once_its_units_are_available_again(self):
		for number in ("101", "102"):
			doc = frappe.get_doc("Unit", {"tower": self.tower, "unit_number": number})
			api.set_inventory_status("Unit", doc.name, "Available")
		structure.remove_tower(self.tower)
		self.assertEqual(frappe.db.get_value("Project Tower", self.tower, "archived"), 1)
		self.assertEqual(self.numbers(), [])
		self.assertEqual(api.get_project(self.project)["towers"], [])
		self.assertTrue(frappe.db.exists("Project Tower", self.tower))  # nothing is deleted

	def test_a_tower_is_never_deleted(self):
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Project Tower", self.tower, force=True)


class TestProjectDetails(StructureCase):
	"""SOS-P7-05: possession date, amenities from the Company Admin's list, and brochure files."""

	def setUp(self):
		super().setUp()
		for name in ("P705 Pool", "P705 Gym"):
			structure.save_amenity(name)
		self.addCleanup(self.remove_brochure_files)

	@staticmethod
	def remove_brochure_files():
		for path in Path(frappe.get_site_path("private", "files")).glob("p705_brochure*"):
			path.unlink()

	def test_the_possession_date_and_amenities_are_saved_and_read_back(self):
		structure.save_project_details(self.project, "2028-03-31", ["P705 Pool", "P705 Gym", "P705 Pool"])
		doc = frappe.get_doc("Project", self.project)
		self.assertEqual(str(doc.possession_date), "2028-03-31")
		self.assertEqual([row.amenity for row in doc.amenities], ["P705 Pool", "P705 Gym"])
		state = api.get_project(self.project)
		self.assertEqual(
			(state["possession_date"], state["amenities"]), ("2028-03-31", ["P705 Pool", "P705 Gym"])
		)
		structure.save_project_details(self.project, "", [])
		self.assertIsNone(frappe.db.get_value("Project", self.project, "possession_date"))

	def test_an_amenity_outside_the_list_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			structure.save_project_details(self.project, None, ["Helipad"])

	def test_only_a_company_admin_edits_the_amenity_list_and_it_is_archived_not_deleted(self):
		structure.save_amenity("P705 Pool", archived=1)
		self.assertNotIn("P705 Pool", structure.amenity_options())
		self.assertTrue(frappe.db.exists("Amenity", "P705 Pool"))
		with self.assertRaises(frappe.ValidationError):
			structure.save_project_details(self.project, None, ["P705 Pool"])
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			structure.save_amenity("P705 Steam")

	def test_a_brochure_is_attached_listed_and_taken_off(self):
		state = structure.add_project_brochure(
			self.project, "Brochure", "p705_brochure.pdf", tiny_pdf_base64()
		)
		self.assertEqual([b["title"] for b in state["brochures"]], ["Brochure"])
		url = state["brochures"][0]["file"]
		self.assertEqual(frappe.db.get_value("File", {"file_url": url}, "is_private"), 1)
		state = structure.remove_project_brochure(self.project, url)
		self.assertEqual(state["brochures"], [])

	def test_a_brochure_that_is_not_a_pdf_or_image_is_refused(self):
		for filename, content in (
			("p705_brochure.exe", tiny_pdf_base64()),
			("p705_brochure.pdf", "bm90IGEgcGRm"),
			("p705_brochure.pdf", "***"),
		):
			with self.subTest(filename=filename), self.assertRaises(frappe.ValidationError):
				structure.add_project_brochure(self.project, "Bad", filename, content)
		self.assertEqual(frappe.get_doc("Project", self.project).brochures, [])


class TestRegressionSeed(InventoryCase):
	"""SOS-P7-05: the regression data holds a project with a tower, floors, units, a date and amenities."""

	def test_the_seed_makes_the_tower_and_is_safe_to_run_again(self):
		from sellos.tests import ui_fixtures

		admin = frappe.session.user
		ui_fixtures._seed_towers(admin)
		ui_fixtures._seed_towers(admin)
		state = ui_fixtures.gate_tower_state("Regression Towers")
		self.assertEqual(
			state,
			{
				"towers": {"Tower A": {"archived": 0, "floors": [1, 2, 3], "units": ["101", "102", "103"]}},
				"possession_date": "2028-03-31",
				"amenities": ["Swimming pool", "Gym"],
			},
		)
