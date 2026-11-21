"""SOS-P4-01: developers, projects, units and properties, their RERA numbers, status log and permissions."""

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.inventory import api
from sellos.inventory.base import clean_rera_number
from sellos.testing.users import TEST_USERS, create_test_users

RERA = "P51800012345"


def _as(key):
	frappe.set_user(TEST_USERS[key]["email"])


class InventoryCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		_as("company_admin")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)

	def make_project(self, name="P401 Tower", rera=RERA, developer="P401 Developer"):
		if not frappe.db.exists("Developer", developer):
			api.save_developer({"developer_name": developer})
		return api.save_project(
			{"project_name": name, "developer": developer, "rera_number": rera, "city": "Mumbai"}
		)["name"]

	def make_unit(self, project, number="1201", **extra):
		values = {"project": project, "unit_number": number, "carpet_area": 640, **extra}
		return api.save_unit(values)["name"]


class TestRecords(InventoryCase):
	"""SOS-P4-01: records are created and edited, and the RERA number is stored for projects."""

	def test_a_developer_project_and_unit_are_made_and_read_back(self):
		project = self.make_project()
		unit = self.make_unit(project, "1201", configuration="2 BHK", floor=12, parking=2)
		doc = frappe.get_doc("Unit", unit)
		self.assertEqual(
			(doc.unit_number, doc.configuration, doc.carpet_area, doc.floor, doc.parking, doc.status),
			("1201", "2 BHK", 640, 12, 2, "Available"),
		)
		self.assertEqual(frappe.db.get_value("Project", project, "developer"), "P401 Developer")

	def test_the_rera_number_is_stored_for_a_project_cleaned(self):
		project = self.make_project(rera=" p518 000 12345 ")
		self.assertEqual(frappe.db.get_value("Project", project, "rera_number"), RERA)

	def test_a_project_needs_a_rera_number_and_a_wrong_one_is_refused(self):
		api.save_developer({"developer_name": "P401 Developer"})
		for rera in ("", "no", "P5180 !! 1"):
			with self.subTest(rera=rera), self.assertRaises(frappe.ValidationError):
				api.save_project(
					{
						"project_name": "P401 Bad",
						"developer": "P401 Developer",
						"rera_number": rera,
						"city": "Mumbai",
					}
				)

	def test_one_rera_number_belongs_to_one_project(self):
		self.make_project("P401 One")
		with self.assertRaises(frappe.ValidationError):
			self.make_project("P401 Two")

	def test_clean_rera_number_is_optional_for_a_property(self):
		self.assertEqual(clean_rera_number(""), "")
		self.assertEqual(
			clean_rera_number("prm/ka/rera/1251/309/pr/190101/000123"),
			"PRM/KA/RERA/1251/309/PR/190101/000123",
		)

	def test_a_project_is_edited(self):
		project = self.make_project()
		api.save_project({"locality": "Powai", "project_status": "Ready to move"}, name=project)
		doc = frappe.get_doc("Project", project)
		self.assertEqual((doc.locality, doc.project_status), ("Powai", "Ready to move"))

	def test_a_unit_number_is_unique_in_a_project_but_not_across_projects(self):
		one = self.make_project("P401 One", rera="P51800000001")
		two = self.make_project("P401 Two", rera="P51800000002")
		self.make_unit(one, "1201")
		with self.assertRaises(frappe.ValidationError):
			self.make_unit(one, " 1201 ")
		self.make_unit(two, "1201")

	def test_a_unit_needs_a_carpet_area_above_zero(self):
		project = self.make_project()
		for area in (0, -5):
			with self.subTest(area=area), self.assertRaises(frappe.ValidationError):
				self.make_unit(project, "9", carpet_area=area)

	def test_numbers_typed_in_the_web_app_arrive_as_text_and_are_saved_as_numbers(self):
		project = self.make_project()
		unit = api.save_unit(
			'{"project": "%s", "unit_number": "7", "carpet_area": "640.5", "floor": "12", "parking": "2"}'
			% project
		)["name"]
		doc = frappe.get_doc("Unit", unit)
		self.assertEqual((doc.carpet_area, doc.floor, doc.parking), (640.5, 12, 2))
		with self.assertRaises(frappe.ValidationError):
			api.save_unit({"project": project, "unit_number": "8", "carpet_area": "0"})

	def test_a_unit_project_is_fixed_once_made(self):
		one = self.make_project("P401 One", rera="P51800000001")
		two = self.make_project("P401 Two", rera="P51800000002")
		unit = self.make_unit(one)
		api.save_unit({"project": two, "floor": 4}, name=unit)
		doc = frappe.get_doc("Unit", unit)
		self.assertEqual((doc.project, doc.floor), (one, 4))

	def test_a_secondary_property_is_made_with_an_optional_rera_number(self):
		made = api.save_property(
			{
				"title": "P401 Resale Flat",
				"property_type": "Apartment",
				"city": "Pune",
				"carpet_area": 480,
				"configuration": "1 BHK",
				"floor": 3,
				"parking": 1,
				"rera_number": "a-1234-5678",
			}
		)
		doc = frappe.get_doc("Property", made["name"])
		self.assertEqual((doc.status, doc.rera_number, doc.parking), ("Available", "A-1234-5678", 1))
		plain = api.save_property(
			{"title": "P401 Plot", "property_type": "Plot", "city": "Pune", "carpet_area": 900}
		)
		self.assertEqual(frappe.db.get_value("Property", plain["name"], "rera_number"), "")

	def test_status_is_not_set_by_a_save(self):
		project = self.make_project()
		unit = self.make_unit(project)
		api.save_unit({"status": "Sold"}, name=unit)
		self.assertEqual(frappe.db.get_value("Unit", unit, "status"), "Available")
		made = api.save_unit({"project": project, "unit_number": "5", "carpet_area": 300, "status": "Sold"})
		self.assertEqual(frappe.db.get_value("Unit", made["name"], "status"), "Available")


class TestStatusLog(InventoryCase):
	"""SOS-P4-01: every unit status change is logged with who and when."""

	def test_a_new_unit_logs_its_first_status(self):
		unit = frappe.get_doc("Unit", self.make_unit(self.make_project()))
		self.assertEqual([(r.from_status, r.to_status) for r in unit.status_log], [("", "Available")])

	def test_each_change_is_logged_with_who_when_and_why(self):
		unit = self.make_unit(self.make_project())
		_as("agent")
		api.set_inventory_status("Unit", unit, "Held", "Buyer asked for a day")
		api.set_inventory_status("Unit", unit, "Sold")
		doc = frappe.get_doc("Unit", unit)
		self.assertEqual(doc.status, "Sold")
		self.assertEqual(
			[(r.from_status, r.to_status, r.changed_by, r.reason) for r in doc.status_log[1:]],
			[
				("Available", "Held", TEST_USERS["agent"]["email"], "Buyer asked for a day"),
				("Held", "Sold", TEST_USERS["agent"]["email"], ""),
			],
		)
		self.assertTrue(all(r.changed_on for r in doc.status_log))

	def test_a_property_status_is_logged_too(self):
		made = api.save_property(
			{"title": "P401 Flat", "property_type": "Apartment", "city": "Pune", "carpet_area": 500}
		)["name"]
		api.set_inventory_status("Property", made, "Held")
		doc = frappe.get_doc("Property", made)
		self.assertEqual([r.to_status for r in doc.status_log], ["Available", "Held"])

	def test_a_change_made_by_a_plain_save_is_logged_as_well(self):
		doc = frappe.get_doc("Unit", self.make_unit(self.make_project()))
		doc.status = "Held"
		doc.save()
		self.assertEqual(
			[r.to_status for r in frappe.get_doc("Unit", doc.name).status_log], ["Available", "Held"]
		)

	def test_an_edit_that_leaves_the_status_adds_no_log_row(self):
		unit = self.make_unit(self.make_project())
		api.save_unit({"floor": 9}, name=unit)
		self.assertEqual(len(frappe.get_doc("Unit", unit).status_log), 1)

	def test_a_wrong_or_repeated_status_is_refused(self):
		unit = self.make_unit(self.make_project())
		for status in ("Booked", "Available"):
			with self.subTest(status=status), self.assertRaises(frappe.ValidationError):
				api.set_inventory_status("Unit", unit, status)
		with self.assertRaises(frappe.ValidationError):
			api.set_inventory_status("Project", unit, "Held")


class TestNothingIsDeleted(InventoryCase):
	"""SOS-P4-01: a record is archived, never deleted."""

	def test_a_delete_is_refused_and_archiving_is_the_company_admins(self):
		project = self.make_project()
		unit = self.make_unit(project)
		for doctype, name in (("Unit", unit), ("Project", project), ("Developer", "P401 Developer")):
			with self.subTest(doctype=doctype), self.assertRaises(frappe.PermissionError):
				frappe.delete_doc(doctype, name)
		api.set_inventory_archived("Unit", unit, 1)
		doc = frappe.get_doc("Unit", unit)
		self.assertEqual((doc.archived, doc.archived_by), (1, TEST_USERS["company_admin"]["email"]))
		self.assertNotIn(unit, [u["name"] for u in api.get_project(project)["units"]])
		api.set_inventory_archived("Unit", unit, 0)
		self.assertIn(unit, [u["name"] for u in api.get_project(project)["units"]])
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			api.set_inventory_archived("Unit", unit, 1)


class TestPermissions(InventoryCase):
	"""SOS-P4-01: only a Company Admin or an Agent edits; a Sales Manager reads; nobody else sees inventory."""

	def setUp(self):
		super().setUp()
		self.project = self.make_project()
		self.unit = self.make_unit(self.project)

	def test_a_company_admin_and_an_agent_edit(self):
		for key in ("company_admin", "agent"):
			_as(key)
			with self.subTest(key=key):
				self.assertTrue(api.inventory_overview()["can_edit"])
				api.save_unit({"floor": 5}, name=self.unit)
				self.assertTrue(frappe.has_permission("Unit", "write", self.unit))

	def test_a_sales_manager_reads_and_edits_nothing(self):
		_as("sales_manager")
		overview = api.inventory_overview()
		self.assertFalse(overview["can_edit"])
		self.assertEqual([p["name"] for p in overview["projects"]], [self.project])
		self.assertEqual(len(api.get_project(self.project)["units"]), 1)
		for call in (
			lambda: api.save_unit({"floor": 8}, name=self.unit),
			lambda: api.save_project({"locality": "x"}, name=self.project),
			lambda: api.set_inventory_status("Unit", self.unit, "Held"),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		for doctype in ("Developer", "Project", "Unit", "Property"):
			self.assertFalse(frappe.has_permission(doctype, "create"), doctype)

	def test_a_client_a_partner_and_the_platform_admin_see_no_inventory(self):
		for key in ("client", "channel_partner", "platform_admin"):
			_as(key)
			for call in (
				api.inventory_overview,
				lambda: api.get_project(self.project),
				lambda: api.save_unit({"floor": 8}, name=self.unit),
			):
				with self.subTest(key=key), self.assertRaises(frappe.PermissionError):
					call()
			for doctype in ("Developer", "Project", "Unit", "Property"):
				self.assertFalse(frappe.has_permission(doctype, "read"), f"{key} {doctype}")

	def test_the_record_permissions_name_no_delete_or_export_for_any_role(self):
		for doctype in ("Developer", "Project", "Unit", "Property"):
			for perm in frappe.get_meta(doctype).permissions:
				self.assertFalse(perm.delete or perm.export, f"{doctype} {perm.role}")

	def test_every_field_is_change_tracked(self):
		for doctype in ("Developer", "Project", "Unit", "Property"):
			self.assertTrue(frappe.get_meta(doctype).track_changes, doctype)


class TestTheRegressionSeed(InventoryCase):
	"""SOS-P4-01: the regression inventory is read back and safe to run twice."""

	def test_the_seed_makes_a_project_with_units_and_a_property(self):
		from sellos.tests import ui_fixtures

		for _ in range(2):
			ui_fixtures._seed_inventory(TEST_USERS["company_admin"]["email"], TEST_USERS["agent"]["email"])
		project = frappe.get_doc("Project", {"project_name": "Regression Heights"})
		self.assertEqual(project.rera_number, "P51800099001")
		statuses = frappe.get_all("Unit", filters={"project": project.name}, pluck="status")
		self.assertEqual(sorted(statuses), ["Available", "Available", "Held", "Sold"])
		self.assertEqual(frappe.db.count("Project", {"project_name": "Regression Heights"}), 1)
		self.assertTrue(frappe.db.exists("Property", {"title": "Regression Resale Flat"}))
