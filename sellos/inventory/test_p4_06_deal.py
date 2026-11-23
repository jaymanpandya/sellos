"""SOS-P4-06: a Deal links a client to a unit or a property at a price, its commission is split among the agent,
the channel partner firm and the company with percents that add up to 100, and a Company Admin approves the split."""

from decimal import Decimal
from unittest.mock import patch

import frappe

from sellos.crm import api as crm
from sellos.crm.test_crm import as_user, email
from sellos.inventory import deals
from sellos.inventory.test_p4_01_inventory import InventoryCase
from sellos.sellos.doctype.deal.deal import split_amounts

COMPANY = {"party_type": "Company", "percent": 100}


def D(text):
	return Decimal(text)


class DealCase(InventoryCase):
	def setUp(self):
		super().setUp()
		self.client_name = crm.save_client(values={"client_name": "P406 Buyer", "client_type": "Buyer"})[
			"name"
		]
		self.unit = self.make_unit(self.make_project(name="P406 Heights", rera="P51800040601"), "1801")
		self.property = frappe.get_doc(
			{
				"doctype": "Property",
				"title": "P406 Flat",
				"property_type": "Apartment",
				"city": "Pune",
				"carpet_area": 500,
			}
		).insert()
		self.firm = self.make_firm("p406_partner@example.com", "P406 Partner Firm")

	def make_firm(self, mail, name, status="Approved"):
		if not frappe.db.exists("User", mail):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": mail,
					"first_name": "P406 Partner",
					"send_welcome_email": 0,
					"roles": [{"role": "SellOS Channel Partner"}],
				}
			)
			user.flags.ignore_permissions = True
			user.insert()
		firm = frappe.get_doc(
			{
				"doctype": "Channel Partner Firm",
				"firm_name": name,
				"contact_user": mail,
				"contact_person": "P406 Contact",
				"email": mail,
			}
		).insert(ignore_permissions=True)
		firm.db_set("status", status)
		return firm.name

	def agent_row(self, percent, who="agent"):
		return {"party_type": "Agent", "agent": email(who), "percent": percent}

	def partner_row(self, percent, firm=None):
		return {"party_type": "Channel Partner", "partner_firm": firm or self.firm, "percent": percent}

	def deal(self, splits=None, **extra):
		as_user("company_admin")
		values = {
			"client": self.client_name,
			"unit": self.unit,
			"price": 10000000,
			"commission_amount": 200000,
			"splits": splits
			if splits is not None
			else [self.agent_row(50), self.partner_row(20), {**COMPANY, "percent": 30}],
			**extra,
		}
		return deals.save_deal(values)["name"]

	def row(self, name):
		as_user("company_admin")
		return next(d for d in deals.deal_overview()["deals"] if d["name"] == name)


class TestDealLinks(DealCase):
	"""SOS-P4-06: a deal links the client and a unit or a property, and the price."""

	def test_a_deal_links_the_client_the_unit_and_the_price_and_waits_for_approval(self):
		name = self.deal()
		doc = frappe.get_doc("Deal", name)
		self.assertEqual(
			(doc.client, doc.unit, doc.property, doc.price), (self.client_name, self.unit, None, 1e7)
		)
		self.assertEqual(doc.approval_status, "Pending approval")
		row = self.row(name)
		self.assertEqual((row["client_name"], row["target"]), ("P406 Buyer", "P406 Heights 1801"))

	def test_a_deal_can_be_for_a_property_instead_of_a_unit(self):
		as_user("company_admin")
		name = deals.save_deal(
			{
				"client": self.client_name,
				"property": self.property.name,
				"price": 5000000,
				"splits": [COMPANY],
			}
		)["name"]
		self.assertEqual(self.row(name)["target"], "P406 Flat")

	def test_a_deal_needs_exactly_one_of_unit_or_property_a_price_and_a_client(self):
		for bad in (
			{"unit": None, "property": None},
			{"property": self.property.name},
			{"price": 0},
			{"client": "no-such-client"},
			{"commission_amount": 20000000},
		):
			with self.assertRaises(frappe.ValidationError, msg=str(bad)):
				self.deal(**bad)
		self.assertEqual(frappe.db.count("Deal", {"client": self.client_name}), 0)

	def test_a_lead_of_another_client_is_refused(self):
		as_user("company_admin")
		other = crm.save_client(values={"client_name": "P406 Other", "client_type": "Buyer"})["name"]
		lead = crm.save_lead(values={"client": other, "source": "Website"})["lead"]["name"]
		with self.assertRaises(frappe.ValidationError):
			self.deal(lead=lead)

	def test_nothing_is_deleted(self):
		name = self.deal()
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Deal", name)
		deals.set_deal_archived(name)
		self.assertEqual(frappe.db.get_value("Deal", name, "archived"), 1)
		self.assertNotIn(name, [d["name"] for d in deals.deal_overview()["deals"]])
		with self.assertRaises(frappe.ValidationError):
			deals.save_deal({"price": 1}, name)


class TestSplitsAddUpTo100(DealCase):
	"""SOS-P4-06: the splits must add up to 100 percent, and every party is named once."""

	def test_a_split_that_does_not_add_up_to_100_is_refused(self):
		for splits in (
			[self.agent_row(50), {**COMPANY, "percent": 49.99}],
			[self.agent_row(60), {**COMPANY, "percent": 41}],
			[self.agent_row(100), {**COMPANY, "percent": 0.01}],
			[],
		):
			with self.assertRaises(frappe.ValidationError, msg=str(splits)):
				self.deal(splits)
		self.assertEqual(frappe.db.count("Deal", {"client": self.client_name}), 0)

	def test_a_split_that_adds_up_to_100_is_saved_even_with_a_third_that_has_no_exact_float(self):
		name = self.deal([self.agent_row(33.33), self.partner_row(33.33), {**COMPANY, "percent": 33.34}])
		self.assertEqual([s["percent"] for s in self.row(name)["splits"]], [33.33, 33.33, 33.34])

	def test_a_share_must_be_above_zero_and_no_party_is_listed_twice(self):
		for splits in (
			[self.agent_row(0), {**COMPANY, "percent": 100}],
			[self.agent_row(-10), {**COMPANY, "percent": 110}],
			[self.agent_row(50), self.agent_row(50)],
			[{**COMPANY, "percent": 50}, {**COMPANY, "percent": 50}],
			[self.partner_row(50), self.partner_row(50)],
		):
			with self.assertRaises(frappe.ValidationError, msg=str(splits)):
				self.deal(splits)

	def test_an_agent_share_needs_an_agent_and_a_partner_share_needs_an_approved_firm(self):
		pending = self.make_firm("p406_pending@example.com", "P406 Pending Firm", status="Pending approval")
		for splits in (
			[{"party_type": "Agent", "percent": 50}, {**COMPANY, "percent": 50}],
			[self.agent_row(50, who="client"), {**COMPANY, "percent": 50}],
			[{"party_type": "Channel Partner", "percent": 50}, {**COMPANY, "percent": 50}],
			[self.partner_row(50, firm=pending), {**COMPANY, "percent": 50}],
			[{"party_type": "Broker", "percent": 100}],
		):
			with self.assertRaises(frappe.ValidationError, msg=str(splits)):
				self.deal(splits)


class TestWorkedSplitExamples(DealCase):
	"""SOS-P4-06: worked examples of how a commission is shared."""

	def test_example_one_a_deal_with_an_agent_a_channel_partner_and_the_company(self):
		# Rs 1,00,00,000 at 2 percent earns Rs 2,00,000: the agent 50, the partner 20, the company 30.
		name = self.deal()
		shares = [(s["party_type"], s["percent"], s["amount"]) for s in self.row(name)["splits"]]
		self.assertEqual(
			shares, [("Agent", 50, 100000), ("Channel Partner", 20, 40000), ("Company", 30, 60000)]
		)

	def test_example_two_a_direct_deal_with_no_partner(self):
		# Rs 50,00,000 at 1.5 percent earns Rs 75,000: the agent 40, the company 60.
		name = self.deal([self.agent_row(40), {**COMPANY, "percent": 60}], commission_amount=75000)
		self.assertEqual(
			[(s["party_type"], s["amount"]) for s in self.row(name)["splits"]],
			[("Agent", 30000), ("Company", 45000)],
		)

	def test_example_three_the_shares_always_add_up_to_the_commission_to_the_paisa(self):
		# Rs 100.01 at 33.33, 33.33 and 33.34 percent rounds to 33.33, 33.33 and 33.34, one paisa short, so the
		# paisa goes to the biggest share.
		shares = split_amounts("100.01", [33.33, 33.33, 33.34])
		self.assertEqual(sum(shares), D("100.01"))
		self.assertEqual(shares, [D("33.33"), D("33.33"), D("33.35")])
		self.assertEqual(split_amounts(0, [50, 50]), [D("0.00"), D("0.00")])
		self.assertEqual(split_amounts("1000", [100]), [D("1000.00")])
		self.assertEqual(split_amounts("0.01", [50, 50]), [D("0.00"), D("0.01")])

	def test_a_channel_partner_share_is_read_back_with_the_firm(self):
		name = self.deal()
		partner = self.row(name)["splits"][1]
		self.assertEqual((partner["partner_firm"], partner["party"]), (self.firm, "P406 Partner Firm"))


class TestApproval(DealCase):
	"""SOS-P4-06: a Company Admin approves the split, and an approved split is not changed."""

	def test_a_company_admin_approves_the_split_and_who_and_when_is_kept(self):
		name = self.deal()
		deals.approve_splits(name)
		row = self.row(name)
		self.assertEqual(row["approval_status"], "Approved")
		self.assertEqual(row["approved_by_name"], "Gate Company Admin")
		self.assertTrue(row["approved_on"])

	def test_nobody_else_approves_or_even_opens_a_deal_method(self):
		name = self.deal()
		for key in ("agent", "sales_manager", "channel_partner", "client", "platform_admin"):
			as_user(key)
			for call in (
				lambda: deals.approve_splits(name),
				lambda: deals.deal_overview(),
				lambda: deals.save_deal({"price": 1}, name),
				lambda: deals.set_deal_archived(name),
				lambda: deals.reopen_splits(name),
			):
				with self.assertRaises(frappe.PermissionError, msg=key):
					call()
		self.assertEqual(frappe.db.get_value("Deal", name, "approval_status"), "Pending approval")

	def test_a_saved_deal_can_not_be_made_approved_by_a_save(self):
		name = self.deal()
		doc = frappe.get_doc("Deal", name)
		doc.approval_status = "Approved"
		with self.assertRaises(frappe.PermissionError):
			doc.save()
		as_user("company_admin")
		deals.save_deal(
			{"approval_status": "Approved", "commission_amount": 150000}, name
		)  # the status is ignored
		self.assertEqual(frappe.db.get_value("Deal", name, "approval_status"), "Pending approval")

	def test_an_approved_split_is_kept_until_it_is_reopened(self):
		name = self.deal()
		deals.approve_splits(name)
		for change in (
			{"price": 9000000},
			{"splits": [self.agent_row(70), {**COMPANY, "percent": 30}]},
		):
			with self.assertRaises(frappe.ValidationError, msg=str(change)):
				deals.save_deal(change, name)
		with self.assertRaises(frappe.ValidationError):
			deals.approve_splits(name)
		deals.reopen_splits(name)
		self.assertEqual(frappe.db.get_value("Deal", name, "approval_status"), "Pending approval")
		self.assertIsNone(frappe.db.get_value("Deal", name, "approved_by"))
		deals.save_deal({"splits": [self.agent_row(70), {**COMPANY, "percent": 30}]}, name)
		self.assertEqual([s["percent"] for s in self.row(name)["splits"]], [70, 30])
		deals.approve_splits(name)
		self.assertEqual(self.row(name)["approval_status"], "Approved")

	def test_the_deal_is_change_tracked_and_has_no_delete_or_export_permission(self):
		meta = frappe.get_meta("Deal")
		self.assertTrue(meta.track_changes)
		self.assertEqual([r.role for r in meta.permissions], ["SellOS Company Admin"])
		for row in meta.permissions:
			self.assertFalse(row.delete or row.export)


class TestRegressionSeed(DealCase):
	"""SOS-P4-06: the regression seed makes an approved deal with a channel partner share and a pending deal,
	and a second run changes nothing."""

	def prerequisites(self):
		"""What the seed reads, made only where the site does not hold it already (all rolled back)."""
		if not frappe.db.exists("Project", {"project_name": "Regression Heights"}):
			project = self.make_project(name="Regression Heights", rera="P51800099777")
			self.make_unit(project, "1201")
		project = frappe.db.get_value("Project", {"project_name": "Regression Heights"}, "name")
		if not frappe.db.exists("Unit", {"project": project, "unit_number": "1201"}):
			self.make_unit(project, "1201")
		if not frappe.db.exists("Property", {"title": "Regression Resale Flat"}):
			frappe.get_doc(
				{
					"doctype": "Property",
					"title": "Regression Resale Flat",
					"property_type": "Apartment",
					"city": "Pune",
					"carpet_area": 720,
				}
			).insert()
		if not frappe.db.exists("Channel Partner Firm", {"firm_name": "Regression Firm Approved"}):
			self.make_firm("p406_regression_firm@example.com", "Regression Firm Approved")
		else:
			frappe.db.set_value(
				"Channel Partner Firm", {"firm_name": "Regression Firm Approved"}, "status", "Approved"
			)

	def test_the_seed_makes_an_approved_and_a_pending_deal_and_a_second_run_changes_nothing(self):
		from sellos.tests import ui_fixtures

		self.prerequisites()
		agent = email("agent")
		before = frappe.db.count("Deal")
		ui_fixtures._seed_deals(email("company_admin"), agent)
		ui_fixtures._seed_deals(email("company_admin"), agent)
		self.assertEqual(frappe.db.count("Deal") - before, 2, "a second run adds none")
		clients = {
			c: frappe.db.get_value("Client", {"client_name": f"Regression Deal Buyer {c}"})
			for c in ("One", "Two")
		}
		one = frappe.get_doc("Deal", {"client": clients["One"]})
		two = frappe.get_doc("Deal", {"client": clients["Two"]})
		self.assertEqual((one.approval_status, two.approval_status), ("Approved", "Pending approval"))
		self.assertEqual(
			[(s.party_type, s.percent, s.amount) for s in one.splits],
			[("Agent", 50, 100000), ("Channel Partner", 20, 40000), ("Company", 30, 60000)],
		)
		self.assertEqual([(s.party_type, s.percent) for s in two.splits], [("Agent", 40), ("Company", 60)])
		self.assertEqual((one.price, two.price), (1e7, 8.2e6))

	def test_the_gate_fixture_for_the_spec_makes_what_the_spec_needs_and_cleans_up(self):
		from sellos.tests import ui_fixtures

		commit = patch.object(
			frappe.db, "commit"
		)  # the fixtures commit for the browser: not inside this test
		commit.start()
		self.addCleanup(commit.stop)
		made = ui_fixtures.make_gate_deal()
		self.assertTrue(frappe.db.exists("Client", {"client_name": made["client"]}))
		self.assertTrue(frappe.db.exists("Property", {"title": made["property"]}))
		self.assertEqual(made["agent"], "Gate Agent")
		client = frappe.db.get_value("Client", {"client_name": made["client"]})
		prop = frappe.db.get_value("Property", {"title": made["property"]})
		as_user("company_admin")
		deals.save_deal({"client": client, "property": prop, "price": 100, "splits": [COMPANY]})
		ui_fixtures.remove_seeded_leads()
		self.assertFalse(frappe.db.exists("Client", client))
		self.assertFalse(frappe.db.exists("Property", prop))
		self.assertEqual(frappe.db.count("Deal", {"client": client}), 0)
