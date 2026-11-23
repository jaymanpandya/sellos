"""SOS-P5-06: the Channel Partner views. Deals, earnings so far, potential earnings and the QR code are the
partner's own; registering a buyer goes through SOS-P7-02's one method; consent never blocks."""

import base64
import json

import frappe

from sellos.access import partner_registrations as pr
from sellos.access.roles import ensure_roles
from sellos.crm import consent, partner_views
from sellos.crm.test_crm import as_user
from sellos.inventory.test_p7_04_commissions import CommissionCase
from sellos.tests import phones

OTHER_MAIL = "p506_other@example.com"


class TestPartnerOverview(CommissionCase):
	"""SOS-P5-06: a partner's deals, earnings so far, potential earnings and QR code."""

	def setUp(self):
		super().setUp()
		self.rate(2)
		self.other = self.make_firm(OTHER_MAIL, "P506 Other Firm")
		self.paid = self.approved_deal(deal_date="2026-03-15")
		self.due = self.approved_deal(deal_date="2026-06-10", share=40)
		self.pending = self.deal(
			[self.agent_row(50), self.partner_row(20), {"party_type": "Company", "percent": 30}],
			deal_date="2026-07-01",
		)
		self.theirs = self.approved_deal(deal_date="2026-03-20", firm=self.other)
		payout = self.payout_of(self.paid)
		self.move(payout, "Approved")
		self.move(payout, "Paid", payment_reference="UTR506001", paid_on="2026-04-02")

	def overview(self, mail=None):
		self.as_partner(mail or "p406_partner@example.com")
		return partner_views.partner_overview()

	def test_earned_so_far_is_the_paid_and_potential_is_the_unpaid(self):
		result = self.overview()
		self.assertEqual(result["earned"], 40000.0)
		self.assertEqual(result["potential"], 80000.0)
		self.assertEqual(result["firm"]["name"], self.firm)

	def test_an_on_hold_payout_is_still_potential(self):
		self.move(self.payout_of(self.due), "On hold", reason="Agreement copy")
		self.assertEqual(self.overview()["potential"], 80000.0)

	def test_the_deals_are_the_partners_own_with_only_their_share(self):
		result = self.overview()
		by_name = {d["name"]: d for d in result["deals"]}
		self.assertEqual(set(by_name), {self.paid, self.due, self.pending})
		self.assertEqual(by_name[self.paid]["payout_status"], "Paid")
		self.assertEqual(by_name[self.paid]["commission_due"], 40000.0)
		self.assertEqual(by_name[self.due]["payout_status"], "Due")
		self.assertEqual(by_name[self.pending]["approval_status"], "Pending approval")
		self.assertEqual(by_name[self.pending]["payout_status"], "")
		text = json.dumps(result, default=str)
		self.assertNotIn(self.theirs, text)
		self.assertNotIn("p406_partner", text.replace(self.firm, ""))  # no login or other party leaks
		for row in result["deals"]:
			self.assertEqual(
				set(row),
				{
					"name",
					"target",
					"deal_date",
					"approval_status",
					"percent",
					"payout_status",
					"commission_due",
				},
			)

	def test_the_other_firm_sees_only_its_own_deal_and_money(self):
		result = self.overview(OTHER_MAIL)
		self.assertEqual([d["name"] for d in result["deals"]], [self.theirs])
		self.assertEqual((result["earned"], result["potential"]), (0.0, 40000.0))

	def test_the_qr_code_is_an_image_of_the_partners_own_link(self):
		mine = self.overview()
		theirs = self.overview(OTHER_MAIL)
		self.assertTrue(mine["link"].endswith(f"/sellos/?partner={self.firm}"))
		self.assertTrue(theirs["link"].endswith(f"/sellos/?partner={self.other}"))
		prefix = "data:image/svg+xml;base64,"
		self.assertTrue(mine["qr"].startswith(prefix))
		self.assertIn("<svg", base64.b64decode(mine["qr"][len(prefix) :]).decode())
		self.assertNotEqual(mine["qr"], theirs["qr"])

	def test_a_firm_that_is_not_approved_sees_nothing(self):
		frappe.db.set_value("Channel Partner Firm", self.firm, "status", "Suspended")
		result = self.overview()
		self.assertEqual((result["firm"], result["deals"], result["qr"]), (None, [], ""))
		self.assertEqual((result["earned"], result["potential"]), (0.0, 0.0))

	def test_nobody_but_a_pure_partner_may_call_it(self):
		for who in ("agent", "company_admin", "client", "sales_manager", "platform_admin"):
			as_user(who)
			with self.assertRaises(frappe.PermissionError, msg=who):
				partner_views.partner_overview()
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			partner_views.partner_overview()

	def test_a_partner_login_with_no_firm_has_nothing(self):
		as_user("channel_partner")
		result = partner_views.partner_overview()
		self.assertEqual((result["firm"], result["deals"], result["earned"]), (None, [], 0.0))

	def test_a_partner_cannot_read_the_deal_itself(self):
		self.as_partner("p406_partner@example.com")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Deal", self.paid).check_permission("read")


class TestRegisteringALead(CommissionCase):
	"""SOS-P5-06: end to end, a partner registers a lead with consent wording through SOS-P7-02's one method."""

	def setUp(self):
		super().setUp()
		ensure_roles()
		self.mail = "p406_partner@example.com"
		self.other = self.make_firm(OTHER_MAIL, "P506 Other Firm")

	def test_a_registered_lead_is_theirs_read_only_masked_and_nobody_elses(self):
		self.as_partner(self.mail)
		form = pr.partner_registration_form()
		self.assertTrue(form["consent_wording"])
		number = phones.in_mobile(5061)
		done = pr.register_buyer("P506 Buyer", number, buyer_agreed=1)
		lead = done["registration"]["lead"]
		self.assertEqual(done["registration"]["consent"]["status"], consent.CONSENTED)
		self.assertIn(lead, frappe.get_list("Lead", pluck="name"))
		doc = frappe.get_doc("Lead", lead)
		self.assertFalse(doc.has_permission("write"))
		text = json.dumps(pr.my_partner_registrations(), default=str)
		for form_of_number in phones.forms(number):
			self.assertNotIn(form_of_number, text)
		self.as_partner(OTHER_MAIL)
		self.assertNotIn(lead, frappe.get_list("Lead", pluck="name"))
		self.assertEqual(pr.my_partner_registrations()["registrations"], [])

	def test_without_the_consent_the_lead_is_saved_unknown_with_a_warning(self):
		self.as_partner(self.mail)
		done = pr.register_buyer("P506 No Consent", phones.in_mobile(5062))
		self.assertTrue(done["accepted"])
		self.assertEqual(done["registration"]["consent"]["status"], consent.UNKNOWN)
		self.assertEqual(done["registration"]["consent"]["warning"], "amber")

	def test_the_next_lead_over_the_limit_is_refused_with_a_message(self):
		frappe.db.set_single_value("SellOS Settings", "partner_lead_limit", 1)
		self.as_partner(self.mail)
		pr.register_buyer("P506 First", phones.in_mobile(5063))
		with self.assertRaises(frappe.TooManyRequestsError) as caught:
			pr.register_buyer("P506 Second", phones.in_mobile(5064))
		self.assertIn("the most the company allows", str(caught.exception))
