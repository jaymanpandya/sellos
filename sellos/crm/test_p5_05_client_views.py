"""SOS-P5-05: the client views. A buyer sees shortlists, visits and deal status; a seller sees mandate status and
the enquiries on their own property as plain rows of four fields; the Dossier is hidden until the mandate is
signed; a client sees only their own data."""

import json

import frappe
from frappe.utils import add_to_date, now_datetime

from sellos.access.roles import CLIENT
from sellos.crm import api, client_views, pipeline
from sellos.crm.test_crm import CrmCase, as_user, email
from sellos.inventory import deals, mandates
from sellos.inventory.test_p4_05_mandate import NAMES, PDF, TERMS, b64
from sellos.tests import phones

SELLER_MAIL = "p505_seller@example.com"
OTHER_SELLER_MAIL = "p505_other_seller@example.com"
BUYER_MAIL = "p505_buyer@example.com"
FOUR = {"label", "stage", "stage_on", "sla"}


def make_user(mail):
	if not frappe.db.exists("User", mail):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": mail,
				"first_name": "P505",
				"send_welcome_email": 0,
				"roles": [{"role": CLIENT}],
			}
		).insert(ignore_permissions=True)
	return mail


class ClientViewCase(CrmCase):
	def setUp(self):
		super().setUp()
		pipeline.ensure_default_stages()
		pipeline.ensure_default_stages(pipeline.SELLER)
		self.seed = 5050
		for mail in (SELLER_MAIL, OTHER_SELLER_MAIL, BUYER_MAIL):
			make_user(mail)

	def phone(self):
		self.seed += 1
		return phones.in_mobile(self.seed)

	def prop(self, title):
		doc = frappe.get_doc(
			{
				"doctype": "Property",
				"title": title,
				"property_type": "Apartment",
				"city": "Pune",
				"carpet_area": 500,
			}
		)
		return doc.insert(ignore_permissions=True).name

	def client(self, name, kind, mail=None):
		as_user("company_admin")
		return api.save_client(
			values={"client_name": name, "client_type": kind, "email": mail, "phone": self.phone()}
		)["name"]

	def lead(self, client, pipeline_name, prop=None, minutes_ago=0):
		as_user("company_admin")
		values = {
			"client": client,
			"source": "Website",
			"pipeline": pipeline_name,
			"assigned_to": email("agent"),
		}
		if prop:
			values["property"] = prop
		name = api.save_lead(values=values)["lead"]["name"]
		frappe.db.set_value(
			"Lead", name, "creation", add_to_date(now_datetime(), minutes=-minutes_ago), update_modified=False
		)
		return name

	def alert(self, lead, resolved=False):
		doc = frappe.get_doc(
			{
				"doctype": "Response Alert",
				"lead": lead,
				"limit_type": "Unassigned",
				"counted_from": now_datetime(),
				"missed_on": now_datetime(),
				"resolved_on": now_datetime() if resolved else None,
			}
		).insert(ignore_permissions=True)
		return doc.name

	def view(self, mail):
		frappe.set_user(mail)
		return client_views.my_overview()


class TestSellerEnquiries(ClientViewCase):
	"""SOS-P5-05: the seller's enquiries are four plain fields and nothing else."""

	def setUp(self):
		super().setUp()
		self.property = self.prop("P505 Tower Flat 12")
		self.other_property = self.prop("P505 Other Flat 7")
		self.seller = self.client("P505 Seller Sunita", "Seller", SELLER_MAIL)
		self.own_lead = self.lead(self.seller, "Seller", self.property, minutes_ago=500)
		self.buyers = []
		for number, ago in enumerate((300, 200, 100), start=1):
			client = self.client(f"P505 Buyer Secretname{number}", "Buyer", f"p505_b{number}@example.com")
			self.buyers.append(self.lead(client, "Buyer", self.property, minutes_ago=ago))
		stray = self.client("P505 Buyer Stray", "Buyer")
		self.stray = self.lead(stray, "Buyer", self.other_property)
		as_user("agent")
		api.move_lead_stage(self.buyers[1], "Contacted")
		self.alert(self.buyers[2], resolved=True)

	def rows(self):
		seller = self.view(SELLER_MAIL)["sellers"]
		self.assertEqual(len(seller), 1)
		return seller[0]["enquiries"]

	def test_the_rows_are_numbered_in_creation_order_and_never_include_the_sellers_own_lead(self):
		rows = self.rows()
		self.assertEqual([r["label"] for r in rows], ["Enquiry 1", "Enquiry 2", "Enquiry 3"])

	def test_a_row_has_exactly_four_fields_and_nothing_else_is_returned(self):
		view = self.view(SELLER_MAIL)
		for row in view["sellers"][0]["enquiries"]:
			self.assertEqual(set(row), FOUR)
		text = json.dumps(view, default=str)
		for lead in (self.own_lead, self.stray, *self.buyers):
			self.assertNotIn(lead, text)
		for secret in ("Secretname", "p505_b", "Stray", self.property, self.other_property, "Website"):
			self.assertNotIn(secret, text)
		for number in frappe.get_all(
			"Client", filters={"client_name": ["like", "P505 Buyer%"]}, pluck="phone"
		):
			self.assertNotIn(number[-10:], text)

	def test_the_stage_and_when_it_was_reached(self):
		rows = self.rows()
		self.assertEqual(rows[0]["stage"], "New")
		self.assertEqual(rows[1]["stage"], "Contacted")
		moved = frappe.get_doc("Lead", self.buyers[1]).stage_log[-1].changed_on
		self.assertEqual(rows[1]["stage_on"], str(moved))
		created = frappe.db.get_value("Lead", self.buyers[0], "creation")
		self.assertEqual(rows[0]["stage_on"], str(created))

	def test_outside_sla_means_at_least_one_response_alert_resolved_or_not(self):
		self.assertEqual([r["sla"] for r in self.rows()], ["In SLA", "In SLA", "Outside SLA"])
		self.alert(self.buyers[0])
		self.assertEqual([r["sla"] for r in self.rows()], ["Outside SLA", "In SLA", "Outside SLA"])

	def test_only_buyer_leads_of_this_property_count_and_archived_ones_do_not(self):
		client = self.client("P505 Buyer Late", "Buyer")
		self.lead(client, "Seller", self.property)  # another seller lead on the same property is no enquiry
		self.assertEqual(len(self.rows()), 3)
		frappe.db.set_value("Lead", self.buyers[0], "archived", 1)
		self.assertEqual(len(self.rows()), 2)

	def test_a_seller_lead_with_no_property_shows_no_rows_and_says_so(self):
		bare = self.client("P505 Seller Bare", "Seller", OTHER_SELLER_MAIL)
		self.lead(bare, "Seller")
		seller = self.view(OTHER_SELLER_MAIL)["sellers"][0]
		self.assertFalse(seller["has_property"])
		self.assertEqual(seller["enquiries"], [])


class TestWhoSeesWhat(ClientViewCase):
	"""SOS-P5-05: a client sees only their own data, and no other role calls the method."""

	def setUp(self):
		super().setUp()
		self.property = self.prop("P505 Shared Flat")
		self.seller = self.client("P505 Seller One", "Seller", SELLER_MAIL)
		self.lead(self.seller, "Seller", self.property)
		self.buyer = self.client("P505 Buyer Own", "Buyer", BUYER_MAIL)
		self.buyer_lead = self.lead(self.buyer, "Buyer", self.property)

	def test_another_seller_sees_none_of_the_rows(self):
		other = self.client("P505 Seller Two", "Seller", OTHER_SELLER_MAIL)
		self.lead(other, "Seller", self.prop("P505 Second Flat"))
		sellers = self.view(OTHER_SELLER_MAIL)["sellers"]
		self.assertEqual([s["enquiries"] for s in sellers], [[]])
		self.assertNotIn("Enquiry", json.dumps(sellers))

	def test_a_buyer_sees_no_seller_rows_and_a_stranger_sees_nothing(self):
		view = self.view(BUYER_MAIL)
		self.assertEqual(view["sellers"], [])
		self.assertEqual(len(view["buyer"]["stages"]), 1)
		frappe.set_user(make_user("p505_nobody@example.com"))
		self.assertEqual(
			client_views.my_overview(),
			{"buyer": {"stages": [], "visits": [], "deals": []}, "shortlists": [], "sellers": []},
		)

	def test_every_other_role_is_refused(self):
		for key in ("channel_partner", "agent", "company_admin", "sales_manager", "platform_admin"):
			as_user(key)
			with self.assertRaises(frappe.PermissionError, msg=key):
				client_views.my_overview()
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			client_views.my_overview()

	def test_a_buyer_sees_own_visits_deal_status_and_shared_shortlists_only(self):
		other = self.client("P505 Buyer Other", "Buyer", "p505_other_buyer@example.com")
		other_lead = self.lead(other, "Buyer", self.property)
		as_user("agent")
		for lead, project in ((self.buyer_lead, "P505 Own Project"), (other_lead, "P505 Their Project")):
			api.save_site_visit(
				values={
					"lead": lead,
					"project_name": project,
					"visit_datetime": add_to_date(now_datetime(), days=2),
					"notes": "P505 agent note",
				}
			)
		as_user("company_admin")
		deals.save_deal(
			{
				"client": self.buyer,
				"property": self.property,
				"price": 5000000,
				"commission_amount": 50000,
				"splits": [{"party_type": "Company", "percent": 100}],
			}
		)
		for client, title, shared in (
			(self.buyer, "P505 Shared", True),
			(self.buyer, "P505 Draft", False),
			(other, "P505 Theirs", True),
		):
			doc = frappe.get_doc(
				{"doctype": "Shortlist", "title": title, "client": client, "agent": email("agent")}
			).insert(ignore_permissions=True)
			if shared:
				frappe.db.set_value("Shortlist", doc.name, "shared_on", now_datetime())
		view = self.view(BUYER_MAIL)
		self.assertEqual([v["project"] for v in view["buyer"]["visits"]], ["P505 Own Project"])
		self.assertEqual(set(view["buyer"]["visits"][0]), {"project", "when", "status", "confirmation"})
		self.assertEqual(
			[(d["target"], d["status"]) for d in view["buyer"]["deals"]], [("P505 Shared Flat", "Booked")]
		)
		self.assertEqual([s["title"] for s in view["shortlists"]], ["P505 Shared"])
		text = json.dumps(view, default=str)
		for leak in ("P505 agent note", "Their Project", "Theirs", "50000", "P505 Draft"):
			self.assertNotIn(leak, text)


class TestTheDossier(ClientViewCase):
	"""SOS-P5-05: the Dossier is hidden until a mandate is signed."""

	def setUp(self):
		super().setUp()
		self.seller = self.client("P505 Seller Dossier", "Seller", SELLER_MAIL)
		self.lead_name = self.lead(self.seller, "Seller", self.prop("P505 Dossier Flat"))
		as_user("agent")
		self.mandate = mandates.save_mandate({"lead": self.lead_name, **TERMS})["name"]
		mandates.add_dossier_note(self.mandate, "Owner's reserve", "Will not go below the reserve.")

	def mandate_view(self):
		return self.view(SELLER_MAIL)["sellers"][0]["mandate"]

	def test_a_draft_mandate_shows_its_status_and_no_dossier(self):
		view = self.mandate_view()
		self.assertEqual((view["status"], view["type"]), ("Draft", "Exclusive"))
		self.assertFalse(view["dossier_released"])
		self.assertEqual(view["dossier"], [])
		self.assertNotIn("reserve", json.dumps(self.view(SELLER_MAIL)))

	def test_a_signed_mandate_releases_the_dossier_titles_but_never_the_notes(self):
		as_user("agent")
		mandates.sign_mandate(self.mandate, NAMES[0], b64(PDF))
		view = self.mandate_view()
		self.assertEqual(view["status"], "Signed")
		self.assertTrue(view["dossier_released"])
		self.assertEqual(view["dossier"], [{"kind": "Note", "title": "Owner's reserve"}])
		self.assertNotIn("Will not go below", json.dumps(self.view(SELLER_MAIL)))

	def test_an_archived_mandate_is_not_shown(self):
		as_user("agent")
		mandates.sign_mandate(self.mandate, NAMES[0], b64(PDF))
		frappe.db.set_value("Mandate", self.mandate, "archived", 1)
		self.assertIsNone(self.mandate_view())
