"""SOS-P7-06: the unit availability grid, holds that expire, blocks, and who sees what."""

import threading
from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, get_datetime

from sellos.crm import api as crm
from sellos.inventory import api, holds, structure
from sellos.inventory.base import STATUSES, UNIT_STATUSES
from sellos.inventory.test_p4_01_inventory import InventoryCase, _as
from sellos.patches import p7_06_unit_statuses
from sellos.testing.users import TEST_USERS
from sellos.tests import phones

NOON = get_datetime("2030-05-01 12:00:00")


class HoldCase(InventoryCase):
	def setUp(self):
		super().setUp()
		self.project = self.make_project("P706 Grid Project", rera="P51800070601", developer="P706 Developer")
		self.tower = structure.add_tower(self.project, "Tower G", "1 to 2")["name"]
		structure.generate_floor_units(self.tower, 1, "101 to 103", 640, "2 BHK", "G")
		structure.generate_floor_units(self.tower, 2, "201 to 201", 480, "1 BHK", "G")
		self.units = {u["unit_number"]: u["name"] for u in api.get_project(self.project)["units"]}
		self.agent = TEST_USERS["agent"]["email"]
		self.lead = self.make_lead(self.agent, 7061)
		self.other_lead = self.make_lead(TEST_USERS["company_admin"]["email"], 7062)
		clock = patch.object(holds, "now", return_value=NOON)
		clock.start()
		self.addCleanup(clock.stop)

	def make_lead(self, owner, seed):
		client = crm.save_client(
			values={
				"client_name": f"P706 Buyer {seed}",
				"client_type": "Buyer",
				"phone": phones.in_mobile(seed),
			}
		)
		return crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": owner})[
			"lead"
		]["name"]

	def unit(self, number):
		return frappe.get_doc("Unit", self.units[number])

	def cell(self, grid, number):
		cells = [u for t in grid["towers"] for f in t["floors"] for u in f["units"]]
		return next(c for c in cells if c["unit_number"] == number)


class TestStatuses(HoldCase):
	"""SOS-P7-06: a unit is Available, Held, Booked, Sold or Blocked; a property keeps three."""

	def test_a_unit_has_five_statuses_and_a_property_three(self):
		self.assertEqual(UNIT_STATUSES, ("Available", "Held", "Booked", "Sold", "Blocked"))
		self.assertEqual(STATUSES, ("Available", "Held", "Sold"))
		options = frappe.get_meta("Unit").get_field("status").options.split("\n")
		self.assertEqual(options, list(UNIT_STATUSES))

	def test_the_patch_changes_no_unit_and_can_run_again(self):
		held = self.units["G101"]
		holds.hold_unit_for(held, self.lead)
		before = {
			u.name: (u.status, u.held_until)
			for u in frappe.get_all("Unit", fields=["name", "status", "held_until"])
		}
		p7_06_unit_statuses.execute()
		p7_06_unit_statuses.execute()
		after = {
			u.name: (u.status, u.held_until)
			for u in frappe.get_all("Unit", fields=["name", "status", "held_until"])
		}
		self.assertEqual(before, after)
		self.assertEqual(frappe.db.get_single_value("SellOS Settings", "unit_hold_hours"), 48)

	def test_booked_is_never_set_from_the_status_change_or_the_grid(self):
		number = "G101"
		for status in ("Booked", "Blocked"):
			with self.subTest(status=status), self.assertRaises(frappe.ValidationError):
				api.set_inventory_status("Unit", self.units[number], status)
		doc = self.unit(number)
		doc.status = "Booked"
		doc.save()  # SOS-P7-10's booking saves the unit itself
		for call in (
			lambda: holds.hold_unit(doc.name, self.lead),
			lambda: holds.block_unit(doc.name, "no"),
			lambda: api.set_inventory_status("Unit", doc.name, "Available"),
		):
			with self.subTest(call=call), self.assertRaises(frappe.ValidationError):
				call()
		self.assertEqual(self.unit(number).status, "Booked")


class TestHolds(HoldCase):
	"""SOS-P7-06: an agent holds an Available unit for their lead, for the company's hold hours."""

	def test_an_agent_holds_a_unit_for_their_lead_for_48_hours_by_default(self):
		_as("agent")
		holds.hold_unit(self.units["G101"], self.lead, "Site visit tomorrow")
		doc = self.unit("G101")
		self.assertEqual(
			(doc.status, doc.held_by, doc.held_for_lead, get_datetime(doc.held_until)),
			("Held", self.agent, self.lead, add_to_date(NOON, hours=48)),
		)
		self.assertEqual(
			[(r.from_status, r.to_status, r.changed_by, r.reason) for r in doc.status_log[1:]],
			[("Available", "Held", self.agent, "Site visit tomorrow")],
		)
		self.assertTrue(doc.status_log[1].changed_on)  # the real time of the change, not the hold clock

	def test_the_hold_hours_setting_sets_how_long_a_hold_lasts(self):
		holds.save_hold_settings(24)
		_as("agent")
		holds.hold_unit(self.units["G101"], self.lead)
		self.assertEqual(get_datetime(self.unit("G101").held_until), add_to_date(NOON, hours=24))

	def test_the_hold_hours_are_checked_and_only_a_company_admin_sets_them(self):
		for hours in (0, -1, 721, "x"):
			with self.subTest(hours=hours), self.assertRaises(frappe.ValidationError):
				holds.save_hold_settings(hours)
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			holds.save_hold_settings(10)

	def test_an_agent_can_not_hold_for_a_lead_they_may_not_see(self):
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			holds.hold_unit(self.units["G101"], self.other_lead)
		with self.assertRaises(frappe.PermissionError):
			holds.hold_unit(self.units["G101"], "NO-SUCH-LEAD")
		self.assertEqual(self.unit("G101").status, "Available")

	def test_a_second_hold_is_refused_with_who_holds_it_and_until_when(self):
		_as("agent")
		holds.hold_unit(self.units["G101"], self.lead)
		_as("company_admin")
		with self.assertRaises(frappe.ValidationError) as caught:
			holds.hold_unit(self.units["G101"], self.other_lead)
		message = str(caught.exception)
		self.assertIn("G101", message)
		self.assertIn(frappe.db.get_value("User", self.agent, "full_name"), message)
		self.assertIn(frappe.utils.format_datetime(add_to_date(NOON, hours=48)), message)
		self.assertEqual(self.unit("G101").held_by, self.agent)

	def test_only_an_available_unit_is_held(self):
		holds.block_unit(self.units["G102"], "Legal")
		for number in ("G102",):
			with self.subTest(number=number), self.assertRaises(frappe.ValidationError):
				holds.hold_unit(self.units[number], self.lead)
		unit = self.unit("G103")
		unit.status = "Sold"
		unit.save()
		with self.assertRaises(frappe.ValidationError):
			holds.hold_unit(unit.name, self.lead)
		with self.assertRaises(frappe.DoesNotExistError):
			holds.hold_unit("NO-SUCH-UNIT", self.lead)

	def test_an_archived_unit_is_not_held(self):
		api.set_inventory_archived("Unit", self.units["G101"], 1)
		with self.assertRaises(frappe.ValidationError):
			holds.hold_unit(self.units["G101"], self.lead)

	def test_a_unit_held_by_the_status_change_has_a_holder_and_an_end(self):
		_as("agent")
		api.set_inventory_status("Unit", self.units["G101"], "Held")
		doc = self.unit("G101")
		self.assertEqual(
			(doc.held_by, get_datetime(doc.held_until)), (self.agent, add_to_date(NOON, hours=48))
		)
		api.set_inventory_status("Unit", self.units["G101"], "Available")
		doc = self.unit("G101")
		self.assertEqual((doc.held_by, doc.held_until, doc.held_for_lead), (None, None, None))


class TestExpiry(HoldCase):
	"""SOS-P7-06: a hold is released when it expires, run as a function with a fixed clock."""

	def hold(self, number="G101"):
		holds.hold_unit_for(self.units[number], self.lead)
		return self.units[number]

	def test_a_hold_is_kept_until_its_end_and_released_after(self):
		unit = self.hold()
		self.assertEqual(holds.expire_holds(add_to_date(NOON, hours=47, minutes=59)), [])
		self.assertEqual(frappe.db.get_value("Unit", unit, "status"), "Held")
		self.assertEqual(holds.expire_holds(add_to_date(NOON, hours=48)), [unit])
		doc = self.unit("G101")
		self.assertEqual(
			(doc.status, doc.held_by, doc.held_until, doc.held_for_lead), ("Available", None, None, None)
		)
		last = doc.status_log[-1]
		self.assertEqual(
			(last.from_status, last.to_status, last.reason), ("Held", "Available", "The hold expired.")
		)
		self.assertTrue(last.changed_by and last.changed_on)

	def test_expiry_leaves_other_statuses_and_unexpired_holds_alone(self):
		later = self.hold("G101")
		holds.block_unit(self.units["G102"], "Legal")
		with patch.object(holds, "now", return_value=add_to_date(NOON, hours=30)):
			sooner = self.hold("G103")
		self.assertEqual(holds.expire_holds(add_to_date(NOON, hours=50)), [later])
		self.assertEqual(frappe.db.get_value("Unit", sooner, "status"), "Held")
		self.assertEqual(self.unit("G102").status, "Blocked")
		self.assertEqual(holds.expire_holds(add_to_date(NOON, hours=50)), [])

	def test_a_lapsed_hold_can_be_held_again_before_the_scheduler_runs(self):
		self.hold()
		with patch.object(holds, "now", return_value=add_to_date(NOON, hours=49)):
			_as("agent")
			holds.hold_unit(self.units["G101"], self.lead)
		doc = self.unit("G101")
		self.assertEqual(
			(doc.status, get_datetime(doc.held_until)), ("Held", add_to_date(NOON, hours=49 + 48))
		)
		self.assertEqual([r.to_status for r in doc.status_log], ["Available", "Held", "Available", "Held"])

	def test_the_grid_shows_a_lapsed_hold_as_available(self):
		self.hold()
		with patch.object(holds, "now", return_value=add_to_date(NOON, hours=49)):
			self.assertEqual(self.cell(holds.unit_grid(self.project), "G101")["status"], "Available")
		self.assertEqual(self.cell(holds.unit_grid(self.project), "G101")["status"], "Held")

	def test_the_scheduler_runs_it(self):
		from sellos import hooks

		self.assertIn("sellos.inventory.holds.expire_holds", hooks.scheduler_events["all"])


class TestRelease(HoldCase):
	"""SOS-P7-06: the holding agent or a Company Admin releases a hold; a Company Admin blocks and unblocks."""

	def test_the_holding_agent_releases_their_hold(self):
		_as("agent")
		holds.hold_unit(self.units["G101"], self.lead)
		holds.release_hold(self.units["G101"], "Buyer changed their mind")
		doc = self.unit("G101")
		self.assertEqual((doc.status, doc.held_by), ("Available", None))
		self.assertEqual(
			(doc.status_log[-1].reason, doc.status_log[-1].changed_by),
			("Buyer changed their mind", self.agent),
		)

	def test_an_agent_can_not_release_another_users_hold_but_a_company_admin_can(self):
		_as("company_admin")
		holds.hold_unit(self.units["G101"], self.other_lead)
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			holds.release_hold(self.units["G101"])
		self.assertEqual(self.unit("G101").status, "Held")
		_as("company_admin")
		holds.release_hold(self.units["G101"])
		self.assertEqual(self.unit("G101").status, "Available")

	def test_a_company_admin_releases_an_agents_hold(self):
		_as("agent")
		holds.hold_unit(self.units["G101"], self.lead)
		_as("company_admin")
		holds.release_hold(self.units["G101"])
		self.assertEqual(self.unit("G101").status, "Available")

	def test_releasing_a_unit_that_is_not_held_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			holds.release_hold(self.units["G101"])

	def test_a_company_admin_blocks_and_unblocks_with_a_reason(self):
		holds.block_unit(self.units["G101"], "  Under   dispute ")
		doc = self.unit("G101")
		self.assertEqual((doc.status, doc.status_log[-1].reason), ("Blocked", "Under dispute"))
		self.assertEqual(self.cell(holds.unit_grid(self.project), "G101")["blocked_reason"], "Under dispute")
		holds.unblock_unit(self.units["G101"], "Dispute settled")
		doc = self.unit("G101")
		self.assertEqual((doc.status, doc.status_log[-1].reason), ("Available", "Dispute settled"))
		self.assertEqual(
			[(r.to_status, r.changed_by) for r in doc.status_log[1:]],
			[
				("Blocked", TEST_USERS["company_admin"]["email"]),
				("Available", TEST_USERS["company_admin"]["email"]),
			],
		)

	def test_a_block_needs_a_reason_and_an_available_unit(self):
		for reason in ("", "   ", None):
			with self.subTest(reason=reason), self.assertRaises(frappe.ValidationError):
				holds.block_unit(self.units["G101"], reason)
		holds.hold_unit_for(self.units["G102"], self.lead)
		with self.assertRaises(frappe.ValidationError):
			holds.block_unit(self.units["G102"], "Legal")
		with self.assertRaises(frappe.ValidationError):
			holds.unblock_unit(self.units["G101"], "Not blocked")
		holds.block_unit(self.units["G101"], "Legal")
		with self.assertRaises(frappe.ValidationError):
			holds.unblock_unit(self.units["G101"], "")

	def test_nobody_but_a_company_admin_blocks_or_unblocks(self):
		for who in ("agent", "sales_manager"):
			_as(who)
			with self.subTest(who=who):
				with self.assertRaises(frappe.PermissionError):
					holds.block_unit(self.units["G101"], "Legal")
				with self.assertRaises(frappe.PermissionError):
					holds.unblock_unit(self.units["G101"], "Legal")

	def test_a_sales_manager_can_not_hold_or_release(self):
		_as("sales_manager")
		with self.assertRaises(frappe.PermissionError):
			holds.hold_unit(self.units["G101"], self.lead)
		with self.assertRaises(frappe.PermissionError):
			holds.release_hold(self.units["G101"])


class TestGrid(HoldCase):
	"""SOS-P7-06: the grid shows each tower's floors and units by status, filtered; the lead only to who may see it."""

	def test_the_grid_lists_floors_top_down_with_units_and_counts(self):
		grid = holds.unit_grid(self.project)
		self.assertEqual(grid["legend"], list(UNIT_STATUSES))
		(tower,) = grid["towers"]
		self.assertEqual([f["floor_number"] for f in tower["floors"]], [2, 1])
		self.assertEqual([u["unit_number"] for u in tower["floors"][1]["units"]], ["G101", "G102", "G103"])
		self.assertEqual(grid["counts"], {"Available": 4, "Held": 0, "Booked": 0, "Sold": 0, "Blocked": 0})
		self.assertEqual(grid["hold_hours"], 48)

	def test_the_grid_filters_by_configuration_and_status(self):
		holds.block_unit(self.units["G102"], "Legal")
		grid = holds.unit_grid(self.project, configuration="1 BHK")
		self.assertEqual(
			[u["unit_number"] for f in grid["towers"][0]["floors"] for u in f["units"]], ["G201"]
		)
		grid = holds.unit_grid(self.project, status="Blocked")
		self.assertEqual(
			[u["unit_number"] for f in grid["towers"][0]["floors"] for u in f["units"]], ["G102"]
		)
		grid = holds.unit_grid(self.project, configuration="1 BHK", status="Blocked")
		self.assertEqual([u["unit_number"] for f in grid["towers"][0]["floors"] for u in f["units"]], [])
		with self.assertRaises(frappe.ValidationError):
			holds.unit_grid(self.project, status="Gone")

	def test_a_unit_with_no_tower_shows_under_other_units(self):
		loose = self.make_unit(self.project, "LOOSE-1")
		grid = holds.unit_grid(self.project)
		self.assertEqual([u["name"] for u in grid["other_units"]], [loose])

	def test_a_held_unit_shows_its_agent_and_the_lead_only_to_who_may_see_it(self):
		_as("agent")
		holds.hold_unit(self.units["G101"], self.lead)
		agent_name = frappe.db.get_value("User", self.agent, "full_name")
		lead_title = frappe.db.get_value("Lead", self.lead, "lead_title")
		for who, sees_lead in (("agent", True), ("company_admin", True), ("sales_manager", False)):
			_as(who)
			with self.subTest(who=who):
				cell = self.cell(holds.unit_grid(self.project), "G101")
				self.assertEqual((cell["status"], cell["held_by_name"]), ("Held", agent_name))
				self.assertEqual(cell["lead_name"], lead_title if sees_lead else "")
				self.assertEqual(cell["lead"], self.lead if sees_lead else "")
		_as("company_admin")
		holds.release_hold(self.units["G101"])
		self.assertEqual(self.cell(holds.unit_grid(self.project), "G101")["held_by"], "")

	def test_the_buttons_a_user_is_offered(self):
		_as("agent")
		holds.hold_unit(self.units["G101"], self.lead)
		grid = holds.unit_grid(self.project)
		mine = self.cell(grid, "G101")
		free = self.cell(grid, "G102")
		self.assertEqual((mine["can_release"], mine["can_hold"]), (True, False))
		self.assertEqual((free["can_hold"], free["can_block"]), (True, False))
		self.assertEqual([lead["name"] for lead in grid["leads"]], [self.lead])
		_as("sales_manager")
		grid = holds.unit_grid(self.project)
		self.assertEqual(
			(grid["can_hold"], grid["leads"], self.cell(grid, "G101")["can_release"]), (False, [], False)
		)
		_as("channel_partner")
		with self.assertRaises(frappe.PermissionError):
			holds.unit_grid(self.project)
		_as("company_admin")
		grid = holds.unit_grid(self.project)
		self.assertTrue(self.cell(grid, "G101")["can_release"] and self.cell(grid, "G102")["can_block"])


class TestConcurrentHolds(HoldCase):
	"""SOS-P7-06: two holds on one unit from two database connections: exactly one succeeds."""

	def test_two_holds_at_the_same_moment_exactly_one_succeeds(self):
		unit = self.units["G101"]
		site, sites_path = frappe.local.site, frappe.local.sites_path
		admin = TEST_USERS["company_admin"]["email"]
		frappe.db.commit()  # the other connections read what this test made  # nosemgrep

		def remove():
			frappe.set_user("Administrator")
			for doctype, filters in (
				("Inventory Status Change", {"parent": ["in", list(self.units.values())]}),
				("Unit", {"project": self.project}),
				("Project Tower", {"project": self.project}),
				("Project", {"name": self.project}),
				("Developer", {"name": "P706 Developer"}),
				("Lead Stage Change", {"parent": ["in", [self.lead, self.other_lead]]}),
				("Lead Assignment", {"lead": ["in", [self.lead, self.other_lead]]}),
				("Lead", {"name": ["in", [self.lead, self.other_lead]]}),
				("Client", {"client_name": ["like", "P706 Buyer %"]}),
			):
				frappe.db.delete(doctype, filters)
			frappe.db.commit()  # nosemgrep

		self.addCleanup(remove)
		start = threading.Barrier(2)
		results = {}

		def attempt(key, lead):
			frappe.init(site, sites_path=sites_path)
			frappe.connect()
			try:
				frappe.set_user(admin)
				start.wait(timeout=30)
				try:
					holds.hold_unit_for(unit, lead)
					frappe.db.commit()  # nosemgrep
					results[key] = "held"
				except frappe.ValidationError as error:
					frappe.db.rollback()
					results[key] = str(error)
			finally:
				frappe.destroy()

		threads = [
			threading.Thread(target=attempt, args=("one", self.lead)),
			threading.Thread(target=attempt, args=("two", self.other_lead)),
		]
		for thread in threads:
			thread.start()
		for thread in threads:
			thread.join(timeout=60)
		outcomes = sorted(results.values(), key=lambda value: value != "held")
		self.assertEqual(len(outcomes), 2)
		self.assertEqual(outcomes[0], "held")
		self.assertIn("is held by", outcomes[1])
		frappe.db.rollback()
		doc = frappe.get_doc("Unit", unit)
		self.assertEqual(doc.status, "Held")
		self.assertEqual([r.to_status for r in doc.status_log], ["Available", "Held"])


class TestRegressionSeed(InventoryCase):
	"""SOS-P7-06: the regression data holds a grid project with a held unit, a blocked unit and Available ones."""

	def test_the_seed_makes_the_grid_and_is_safe_to_run_again(self):
		from sellos.tests import ui_fixtures

		agent = TEST_USERS["agent"]["email"]
		lead = crm.save_client(
			values={
				"client_name": "Regression Buyer One",
				"client_type": "Buyer",
				"phone": phones.in_mobile(7063),
			}
		)
		made = crm.save_lead(values={"client": lead["name"], "source": "Website", "assigned_to": agent})
		ui_fixtures._seed_towers(frappe.session.user)
		ui_fixtures._seed_unit_grid(frappe.session.user, agent)
		ui_fixtures._seed_unit_grid(frappe.session.user, agent)
		project = frappe.db.get_value("Project", {"project_name": "Regression Grid"}, "name")
		grid = holds.unit_grid(project)
		cells = {u["unit_number"]: u for t in grid["towers"] for f in t["floors"] for u in f["units"]}
		self.assertEqual(
			{number: cell["status"] for number, cell in cells.items()},
			{
				"G101": "Available",
				"G102": "Held",
				"G103": "Available",
				"G104": "Blocked",
				"G201": "Available",
			},
		)
		self.assertEqual(cells["G102"]["held_by"], agent)
		self.assertEqual(cells["G102"]["lead"], made["lead"]["name"])
		self.assertEqual(cells["G102"]["configuration"], "3 BHK")
		self.assertEqual(cells["G104"]["blocked_reason"], "Regression: legal hold")
