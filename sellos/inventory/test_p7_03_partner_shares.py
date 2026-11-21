"""SOS-P7-03: share projects, units and collateral with channel partners."""

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.inventory import api, partner_shares, pricing
from sellos.testing.users import TEST_USERS, create_test_users

FIRM = "Channel Partner Firm"
SHARE = "Partner Share"
OTHER_PARTNER = "p703_other_partner@example.com"
PRICE_LIST = {
	"title": "P703 List",
	"effective_from": "2020-01-01",
	"base_rate": 11000,
	"floor_rise_rate": 50,
	"floor_rise_from_floor": 2,
	"charges": [],
}


def _as(who):
	frappe.set_user(TEST_USERS[who]["email"] if who in TEST_USERS else who)


class TestPartnerShares(IntegrationTestCase):
	"""SOS-P7-03: a partner of each of two firms sees exactly what is shared with their firm."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		self.firm_a = self.make_firm(TEST_USERS["channel_partner"]["email"], "P703 Firm A")
		self.firm_b = self.make_firm(OTHER_PARTNER, "P703 Firm B")
		_as("company_admin")
		api.save_developer({"developer_name": "P703 Developer"})
		self.one = self.make_project("P703 One", "P51800070301")
		self.two = self.make_project("P703 Two", "P51800070302")
		self.units = [
			api.save_unit({"project": self.one, "unit_number": n, "carpet_area": 600})["name"]
			for n in ("101", "102", "103")
		]
		self.other_unit = api.save_unit({"project": self.two, "unit_number": "201", "carpet_area": 700})[
			"name"
		]
		pricing.save_price_list(self.one, PRICE_LIST)
		pricing.save_price_list(self.two, {**PRICE_LIST, "title": "P703 Two List"})
		self.brochure = self.make_asset("P703 Brochure")
		self.brochure_two = self.make_asset("P703 Second")

	def make_project(self, name, rera):
		return api.save_project(
			{"project_name": name, "developer": "P703 Developer", "rera_number": rera, "city": "Pune"}
		)["name"]

	def make_asset(self, title):
		return (
			frappe.get_doc(
				{
					"doctype": "Media Asset",
					"title": title,
					"media_type": "Photo",
					"file": f"/files/{title}.jpg",
				}
			)
			.insert()
			.name
		)

	def make_firm(self, email, name, status="Approved"):
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "P703 Other",
					"send_welcome_email": 0,
					"roles": [{"role": "SellOS Channel Partner"}],
				}
			)
			user.flags.ignore_permissions = True
			user.insert()
		firm = frappe.get_doc(
			{
				"doctype": FIRM,
				"firm_name": name,
				"contact_user": email,
				"contact_person": "P703 Contact",
				"email": email,
			}
		).insert(ignore_permissions=True)
		firm.db_set("status", status)
		return firm.name

	def share(self, project, firms, **kw):
		_as("company_admin")
		return partner_shares.share_project(project, firms, **kw)

	def as_partner(self, who="channel_partner"):
		_as(who)

	def seen(self, who):
		self.as_partner(who)
		return {p["name"] for p in partner_shares.my_shared_projects()["projects"]}

	def test_each_of_two_firms_sees_exactly_what_is_shared_with_its_own(self):
		self.share(
			self.one, [self.firm_a], units=self.units[:2], share_price_list=1, brochures=[self.brochure]
		)
		self.share(self.two, [self.firm_b])
		self.as_partner()
		listed = partner_shares.my_shared_projects()["projects"]
		self.assertEqual([p["name"] for p in listed], [self.one])
		self.assertEqual(
			(listed[0]["units"], listed[0]["has_price_list"], listed[0]["brochures"]), (2, True, 1)
		)
		detail = partner_shares.my_shared_project(self.one)
		self.assertEqual(sorted(u["name"] for u in detail["units"]), sorted(self.units[:2]))
		self.assertEqual(detail["price_list"]["base_rate"], 11000)
		self.assertEqual([b["name"] for b in detail["brochures"]], [self.brochure])
		with self.assertRaises(frappe.DoesNotExistError):
			partner_shares.my_shared_project(self.two)
		self.as_partner(OTHER_PARTNER)
		self.assertEqual([p["name"] for p in partner_shares.my_shared_projects()["projects"]], [self.two])
		other = partner_shares.my_shared_project(self.two)
		self.assertEqual(len(other["units"]), 1)
		self.assertIsNone(other["price_list"])
		self.assertEqual(other["brochures"], [])
		with self.assertRaises(frappe.DoesNotExistError):
			partner_shares.my_shared_project(self.one)

	def test_a_share_with_every_approved_firm_reaches_both_and_all_units(self):
		self.share(self.one, "all")
		for who in ("channel_partner", OTHER_PARTNER):
			self.as_partner(who)
			units = partner_shares.my_shared_project(self.one)["units"]
			self.assertEqual(len(units), 3)
		self.assertEqual(frappe.db.count(SHARE, {"project": self.one}), 1)

	def test_shares_to_one_firm_are_merged(self):
		self.share(self.one, [self.firm_a], units=[self.units[0]])
		self.share(self.one, [self.firm_a], units=[self.units[1]], brochures=[self.brochure_two])
		self.as_partner()
		detail = partner_shares.my_shared_project(self.one)
		self.assertEqual(sorted(u["name"] for u in detail["units"]), sorted(self.units[:2]))
		self.assertEqual([b["name"] for b in detail["brochures"]], [self.brochure_two])
		self.assertIsNone(detail["price_list"])

	def test_a_withdrawn_share_stops_showing_at_once_and_is_logged(self):
		name = self.share(self.one, [self.firm_a])["shares"][0]["name"]
		self.assertEqual(self.seen("channel_partner"), {self.one})
		_as("company_admin")
		result = partner_shares.withdraw_partner_share(name, "p703 done")
		self.assertEqual(result["shares"][0]["status"], "Withdrawn")
		self.assertEqual(self.seen("channel_partner"), set())
		_as("company_admin")
		log = [(r["action"], r["detail"]) for r in result["shares"][0]["log"]]
		self.assertEqual([a for a, _d in log], ["Shared", "Withdrawn"])
		self.assertEqual(log[1][1], "p703 done")
		doc = frappe.get_doc(SHARE, name)
		self.assertEqual(doc.withdrawn_by, TEST_USERS["company_admin"]["email"])
		self.assertTrue(doc.withdrawn_on)
		with self.assertRaises(frappe.ValidationError):
			partner_shares.update_partner_share(name, [self.units[0]])
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(SHARE, name)

	def test_a_suspended_firm_sees_nothing_and_is_refused(self):
		self.share(self.one, [self.firm_a])
		frappe.db.set_value(FIRM, self.firm_a, "status", "Suspended")
		self.as_partner()
		with self.assertRaises(frappe.PermissionError):
			partner_shares.my_shared_projects()
		with self.assertRaises(frappe.PermissionError):
			partner_shares.my_shared_project(self.one)
		frappe.db.set_value(FIRM, self.firm_a, "status", "Approved")
		self.assertEqual(self.seen("channel_partner"), {self.one})

	def test_a_firm_that_is_not_approved_can_not_be_shared_with(self):
		pending = self.make_firm("p703_pending@example.com", "P703 Pending", "Pending approval")
		with self.assertRaises(frappe.ValidationError):
			self.share(self.one, [pending])

	def test_a_change_of_units_and_price_list_is_logged_and_shows_at_once(self):
		name = self.share(self.one, [self.firm_a])["shares"][0]["name"]
		_as("company_admin")
		result = partner_shares.update_partner_share(name, [self.units[2]], 1, [self.brochure])
		self.assertEqual([r["action"] for r in result["shares"][0]["log"]], ["Shared", "Changed"])
		self.as_partner()
		detail = partner_shares.my_shared_project(self.one)
		self.assertEqual([u["name"] for u in detail["units"]], [self.units[2]])
		self.assertTrue(detail["price_list"])

	def test_the_unit_and_brochure_must_belong_and_be_live(self):
		with self.assertRaises(frappe.ValidationError):
			self.share(self.one, [self.firm_a], units=[self.other_unit])
		frappe.db.set_value("Media Asset", self.brochure, "archived", 1)
		with self.assertRaises(frappe.ValidationError):
			self.share(self.one, [self.firm_a], brochures=[self.brochure])

	def test_archived_records_stop_showing(self):
		self.share(self.one, [self.firm_a], brochures=[self.brochure])
		frappe.db.set_value("Unit", self.units[0], "archived", 1)
		frappe.db.set_value("Media Asset", self.brochure, "archived", 1)
		self.as_partner()
		detail = partner_shares.my_shared_project(self.one)
		self.assertEqual(len(detail["units"]), 2)
		self.assertEqual(detail["brochures"], [])
		frappe.db.set_value("Project", self.one, "archived", 1)
		self.assertEqual(self.seen("channel_partner"), set())

	def test_a_price_list_shown_is_the_one_in_force(self):
		self.share(self.one, [self.firm_a], share_price_list=1)
		_as("company_admin")
		pricing.save_price_list(
			self.one,
			{**PRICE_LIST, "title": "P703 Newer", "effective_from": "2021-01-01", "base_rate": 12500},
		)
		self.as_partner()
		self.assertEqual(partner_shares.my_shared_project(self.one)["price_list"]["base_rate"], 12500)

	def test_a_partner_reads_no_inventory_or_share_record_directly(self):
		self.share(self.one, [self.firm_a])
		self.as_partner()
		for doctype in ("Project", "Unit", "Price List", "Media Asset", SHARE):
			with self.subTest(doctype=doctype):
				try:
					self.assertEqual(frappe.get_list(doctype), [])
				except frappe.PermissionError:
					pass
		for method in (
			lambda: api.inventory_overview(),
			lambda: api.get_project(self.one),
			lambda: pricing.project_pricing(self.one),
			lambda: partner_shares.list_partner_shares(),
			lambda: partner_shares.share_project(self.one, "all"),
			lambda: partner_shares.withdraw_partner_share("SHR-00001"),
		):
			with self.assertRaises(frappe.PermissionError):
				method()

	def test_the_partner_answers_name_no_other_firm_or_registration(self):
		self.share(self.one, [self.firm_a])
		self.share(self.one, [self.firm_b])
		self.as_partner()
		text = frappe.as_json(
			[partner_shares.my_shared_projects(), partner_shares.my_shared_project(self.one)]
		)
		for leak in (self.firm_b, "P703 Firm B", OTHER_PARTNER, "registration", "SHR-"):
			self.assertNotIn(leak, text)

	def test_no_other_role_shares_and_only_a_company_admin_reads_shares(self):
		for who in ("agent", "sales_manager", "client", "platform_admin"):
			_as(who)
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				partner_shares.share_project(self.one, "all")
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				partner_shares.my_shared_projects()


class TestPartnerShareSeed(IntegrationTestCase):
	"""SOS-P7-03: the regression seed and the spec helpers make shares through the production methods."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)

	def test_the_regression_seed_makes_three_shares_and_withdraws_one(self):
		from sellos.tests import ui_fixtures

		admin, agent = TEST_USERS["company_admin"]["email"], TEST_USERS["agent"]["email"]
		ui_fixtures._seed_partner_firms(admin)
		ui_fixtures._seed_inventory(admin, agent)
		ui_fixtures._seed_partner_shares(admin)
		ui_fixtures._seed_partner_shares(admin)
		rows = frappe.get_all("Partner Share", fields=["project", "status", "all_firms", "all_units"])
		by_project = {frappe.db.get_value("Project", r.project, "project_name"): r for r in rows}
		self.assertEqual(
			{k: (r.status, r.all_firms, r.all_units) for k, r in by_project.items()},
			{
				"Regression Pricing": ("Active", 0, 1),
				"Regression Heights": ("Active", 1, 0),
				"Regression Grid": ("Withdrawn", 0, 1),
			},
		)

	def test_the_spec_helpers_make_and_read_back_shares_and_the_cleanup_removes_them(self):
		from sellos.tests import ui_fixtures

		ui_fixtures.remove_gate_partner_shares()
		made = ui_fixtures.make_gate_partner_shares()
		self.assertEqual(len(made["projects"]), 2)
		_as("company_admin")
		partner_shares.share_project(made["projects"][0], "all", brochures=[made["brochure"]])
		state = ui_fixtures.gate_partner_shares_state(made["projects"][0])
		self.assertEqual(state, [("Active", ["Shared"])])
		ui_fixtures.remove_gate_partner_shares()
		self.assertEqual(frappe.db.count("Partner Share"), 0)
		self.assertEqual(frappe.db.count("Media Asset", {"title": ["like", "Gate Inventory %"]}), 0)
