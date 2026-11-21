"""SOS-P7-01: invite, complete, approve, suspend and reinstate channel partner firms."""

import base64
import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access import field_history, lead_permissions, partner_firms, users
from sellos.access.roles import CHANNEL_PARTNER, ensure_roles
from sellos.crm import pipeline
from sellos.sellos.doctype.channel_partner_firm.channel_partner_firm import clean_pan, clean_rera
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones
from sellos.tests.files import tiny_pdf_base64

FIRM = "Channel Partner Firm"
RERA = "A51800012345"
PAN = "ABCPD1234E"
PHONE = phones.in_mobile(7011)
AGREEMENT = tiny_pdf_base64()
FILE_NAME = "p701_test_agreement.pdf"


def _email(key):
	return TEST_USERS[key]["email"]


def _as(key_or_email):
	frappe.set_user(TEST_USERS[key_or_email]["email"] if key_or_email in TEST_USERS else key_or_email)


class PartnerFirmCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()
		pipeline.ensure_default_stages()

	def setUp(self):
		_as("company_admin")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		self.addCleanup(self._remove_files)
		self.counter = 0

	@staticmethod
	def _remove_files():
		for path in Path(frappe.get_site_path("private", "files")).glob("p701_test_agreement*"):
			path.unlink()

	def invite(self, name="P701 Firm One", email="p701_one@example.com", phone=""):
		with (
			patch.object(users, "mail_ready", return_value=True),
			patch("frappe.sendmail", side_effect=lambda **kw: self.sent.append(kw)),
		):
			return partner_firms.invite_partner_firm(name, "P701 Contact", email, phone)

	@property
	def sent(self):
		if not hasattr(self, "_sent"):
			self._sent = []
		return self._sent

	def complete(self, code, email, **extra):
		"""What the contact person does after signing in: the details, then the agreement."""
		_as(email)
		values = {"phone": PHONE, "rera_number": RERA, "pan": PAN, **extra}
		partner_firms.submit_partner_details(values)
		result = partner_firms.upload_my_agreement(FILE_NAME, AGREEMENT)
		_as("company_admin")
		return result

	def ready_firm(self, name="P701 Firm One", email="p701_one@example.com"):
		code = self.invite(name, email)["name"]
		self.complete(code, email)
		return code


class TestInvitation(PartnerFirmCase):
	def test_a_company_admin_invites_a_firm_and_its_contact_gets_a_partner_login(self):
		result = self.invite()
		self.assertTrue(result["invited"])
		self.assertEqual(frappe.get_roles("p701_one@example.com").count(CHANNEL_PARTNER), 1)
		firm = frappe.get_doc(FIRM, result["name"])
		self.assertEqual(firm.status, "Invited")
		self.assertEqual(firm.contact_user, "p701_one@example.com")
		self.assertEqual(firm.owner, _email("company_admin"))
		self.assertIn("p701_one@example.com", self.sent[-1]["recipients"])
		self.assertIn("key=", self.sent[-1]["message"])  # SOS-P1-17's link to set a password

	def test_the_contact_person_completes_the_details_and_the_firm_moves_to_pending_approval(self):
		code = self.invite()["name"]
		_as("p701_one@example.com")
		first = partner_firms.submit_partner_details({"phone": PHONE, "rera_number": RERA, "pan": PAN})
		self.assertEqual(first["firm"]["status"], "Invited")  # no agreement yet
		self.assertEqual(first["firm"]["missing"], ["signed agreement"])
		done = partner_firms.upload_my_agreement(FILE_NAME, AGREEMENT)
		self.assertEqual(done["firm"]["status"], "Pending approval")
		self.assertTrue(done["firm"]["has_agreement"])
		self.assertEqual(frappe.db.get_value(FIRM, code, "status"), "Pending approval")

	def test_a_duplicate_firm_name_an_existing_login_and_a_bad_email_are_refused(self):
		self.invite()
		with self.assertRaises(frappe.ValidationError):
			self.invite(name="P701 Firm One", email="p701_two@example.com")
		with self.assertRaises(frappe.ValidationError):
			self.invite(name="P701 Firm Two", email="p701_one@example.com")
		with self.assertRaises(frappe.ValidationError):
			self.invite(name="P701 Firm Three", email="not an email")

	def test_only_a_company_admin_invites(self):
		for key in ("agent", "channel_partner", "sales_manager", "client", "platform_admin"):
			_as(key)
			with self.subTest(key), self.assertRaises(frappe.PermissionError):
				partner_firms.invite_partner_firm("P701 Nope", "P701 Nope", "p701_nope@example.com")


class TestApproval(PartnerFirmCase):
	def test_a_company_admin_approves_suspends_and_reinstates_and_each_move_is_logged(self):
		code = self.ready_firm()
		partner_firms.approve_partner_firm(code)
		with self.assertRaises(frappe.ValidationError):
			partner_firms.suspend_partner_firm(code, "  ")  # a reason is needed
		partner_firms.suspend_partner_firm(code, "Left the business")
		firm = frappe.get_doc(FIRM, code)
		self.assertEqual((firm.status, firm.status_reason), ("Suspended", "Left the business"))
		partner_firms.reinstate_partner_firm(code)
		firm.reload()
		self.assertEqual((firm.status, firm.status_reason), ("Approved", ""))
		moves = [(r.from_status, r.to_status, r.changed_by) for r in firm.status_log]
		admin = _email("company_admin")
		self.assertEqual(
			moves,
			[
				("", "Invited", admin),
				("Invited", "Pending approval", "p701_one@example.com"),
				("Pending approval", "Approved", admin),
				("Approved", "Suspended", admin),
				("Suspended", "Approved", admin),
			],
		)
		self.assertTrue(all(r.changed_on for r in firm.status_log))
		self.assertEqual(firm.status_log[3].reason, "Left the business")

	def test_only_a_company_admin_approves_suspends_or_reinstates(self):
		code = self.ready_firm()
		for key in ("agent", "channel_partner", "sales_manager", "client", "platform_admin"):
			_as(key)
			for call in (
				lambda: partner_firms.approve_partner_firm(code),
				lambda: partner_firms.suspend_partner_firm(code, "no"),
				lambda: partner_firms.reinstate_partner_firm(code),
			):
				with self.subTest(key), self.assertRaises(frappe.PermissionError):
					call()
		self.assertEqual(frappe.db.get_value(FIRM, code, "status"), "Pending approval")

	def test_a_firm_that_has_not_completed_its_details_can_not_be_approved(self):
		code = self.invite()["name"]
		with self.assertRaises(frappe.ValidationError):
			partner_firms.approve_partner_firm(code)  # Invited is not Pending approval

	def test_the_status_can_not_be_edited_directly(self):
		code = self.ready_firm()
		firm = frappe.get_doc(FIRM, code)
		firm.status = "Approved"
		with self.assertRaises(frappe.PermissionError):
			firm.save()

	def test_a_partner_can_not_change_the_details_once_approved(self):
		code = self.ready_firm()
		partner_firms.approve_partner_firm(code)
		_as("p701_one@example.com")
		with self.assertRaises(frappe.PermissionError):
			partner_firms.submit_partner_details({"pan": PAN})
		with self.assertRaises(frappe.PermissionError):
			partner_firms.upload_my_agreement(FILE_NAME, AGREEMENT)

	def test_nothing_is_deleted(self):
		code = self.ready_firm()
		partner_firms.suspend_partner_firm(code, "Left")
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(FIRM, code, force=True)
		self.assertTrue(frappe.db.exists(FIRM, code))


class TestNoWorkUntilApproved(PartnerFirmCase):
	def lead_for(self, email):
		client = frappe.get_doc({"doctype": "Client", "client_name": "P701 Buyer", "client_type": "Buyer"})
		client.insert()
		lead = frappe.get_doc({"doctype": "Lead", "client": client.name, "source": "Website"})
		lead.insert()
		frappe.db.set_value("Lead", lead.name, "assigned_to", email)
		return lead.name

	def test_an_unapproved_partner_registers_and_sees_no_lead_and_an_approved_one_does(self):
		code = self.ready_firm()
		email = "p701_one@example.com"
		lead = self.lead_for(email)
		for status in ("Pending approval", "Suspended"):
			frappe.db.set_value(FIRM, code, "status", status)
			self.assertEqual(lead_permissions._user_scope(email), "none", status)
			_as(email)
			self.assertFalse(partner_firms.partner_may_work(), status)
			self.assertEqual(frappe.get_list("Lead", pluck="name"), [], status)
			self.assertFalse(frappe.has_permission("Lead", "read", doc=lead), status)
			self.assertFalse(frappe.has_permission("Lead", "create", doc=frappe.new_doc("Lead")), status)
			_as("company_admin")
		_as("company_admin")
		frappe.db.set_value(FIRM, code, "status", "Approved")
		self.assertEqual(lead_permissions._user_scope(email), "own")
		_as(email)
		self.assertTrue(partner_firms.partner_may_work())
		self.assertEqual(frappe.get_list("Lead", pluck="name"), [lead])
		# SOS-P7-02: an approved partner makes a lead only through register_buyer and changes nothing after.
		self.assertFalse(frappe.has_permission("Lead", "create", doc=frappe.new_doc("Lead")))

	def test_the_partner_is_told_the_state_of_the_firm(self):
		code = self.ready_firm()
		partner_firms.approve_partner_firm(code)
		partner_firms.suspend_partner_firm(code, "Agreement ended")
		_as("p701_one@example.com")
		firm = partner_firms.my_partner_firm()["firm"]
		self.assertEqual((firm["status"], firm["status_reason"]), ("Suspended", "Agreement ended"))
		self.assertFalse(firm["can_work"])

	def test_a_login_with_no_firm_is_not_held_back(self):
		self.assertTrue(partner_firms.partner_may_work(_email("channel_partner")))
		_as("channel_partner")
		self.assertIsNone(partner_firms.my_partner_firm()["firm"])
		with self.assertRaises(frappe.PermissionError):
			partner_firms.submit_partner_details({"pan": PAN})


class TestPartnerCode(PartnerFirmCase):
	def test_each_firm_has_a_unique_code_that_is_never_reused(self):
		first = self.invite("P701 Code A", "p701_a@example.com")["name"]
		second = self.invite("P701 Code B", "p701_b@example.com")["name"]
		self.assertNotEqual(first, second)
		self.assertRegex(first, r"^CP-\d{5}$")
		self.assertEqual(frappe.db.get_value(FIRM, first, "partner_code"), first)
		self.assertGreater(int(second[3:]), int(first[3:]))
		# A firm that leaves is Suspended, not deleted, so its code stays taken and the next is higher.
		partner_firms.suspend_partner_firm(first, "Left")
		third = self.invite("P701 Code C", "p701_c@example.com")["name"]
		self.assertGreater(int(third[3:]), int(second[3:]))
		self.assertEqual(frappe.db.count(FIRM, {"partner_code": first}), 1)

	def test_the_code_can_not_be_changed(self):
		code = self.invite()["name"]
		firm = frappe.get_doc(FIRM, code)
		firm.partner_code = "CP-99999"
		firm.save()
		self.assertEqual(frappe.db.get_value(FIRM, code, "partner_code"), code)


class TestFormats(PartnerFirmCase):
	def test_the_rera_number_is_checked_for_format(self):
		self.assertEqual(clean_rera(" a51800012345 "), RERA)
		self.assertEqual(clean_rera("PRM/KA/RERA/1251/309/AG/190101/000123").count("/"), 7)
		self.assertEqual(clean_rera(""), "")
		for bad in ("A5180001234", "B51800012345", "12345", "A518-0001", "RERA!!"):
			with self.subTest(bad), self.assertRaises(frappe.ValidationError):
				clean_rera(bad)

	def test_the_pan_is_checked_for_format(self):
		self.assertEqual(clean_pan(" abcpd1234e "), PAN)
		self.assertEqual(clean_pan(""), "")
		for bad in ("ABCDE1234F", "ABCPD12345", "ABCPD123E", "1BCPD1234E", "ABCPD1234"):
			with self.subTest(bad), self.assertRaises(frappe.ValidationError):
				clean_pan(bad)

	def test_a_bad_format_is_refused_when_the_partner_submits(self):
		self.invite()
		_as("p701_one@example.com")
		for values in ({"rera_number": "nope"}, {"pan": "nope"}, {"phone": "12345"}):
			with self.subTest(values), self.assertRaises(frappe.ValidationError):
				partner_firms.submit_partner_details(values)

	def test_the_phone_is_a_valid_indian_mobile_and_stored_in_full(self):
		code = self.ready_firm()
		self.assertEqual(frappe.db.get_value(FIRM, code, "phone"), PHONE)

	def test_the_agreement_must_be_a_pdf_or_image_of_a_reasonable_size(self):
		self.invite()
		_as("p701_one@example.com")
		other = base64.b64encode(b"MZ not a document").decode()
		for name, content in ((FILE_NAME, other), ("p701_test_agreement.exe", AGREEMENT), (FILE_NAME, "%%%")):
			with self.subTest(name), self.assertRaises(frappe.ValidationError):
				partner_firms.upload_my_agreement(name, content)


class TestWhoSeesWhat(PartnerFirmCase):
	def getdoc_text(self, code):
		frappe.local.response = frappe._dict({"docs": []})
		field_history.getdoc(FIRM, code)
		return json.dumps([d.as_dict() for d in frappe.response["docs"]], default=str)

	def test_the_pan_the_agreement_and_the_full_phone_are_a_company_admins_alone(self):
		code = self.ready_firm()
		url = frappe.db.get_value(FIRM, code, "agreement")
		_as("company_admin")
		text = self.getdoc_text(code)
		self.assertIn(PAN, text)
		self.assertIn(PHONE, text)
		self.assertIn(url, text)
		admin_view = partner_firms.list_partner_firms()["firms"][0]
		self.assertEqual((admin_view["pan"], admin_view["phone"], admin_view["agreement"]), (PAN, PHONE, url))
		# The contact person reads the firm, and gets no PAN, no agreement and a masked phone.
		_as("p701_one@example.com")
		text = self.getdoc_text(code)
		for secret in (PAN, url, *phones.forms(PHONE)):
			self.assertNotIn(secret, text)
		self.assertIn("phone_masked", text)
		own = json.dumps(partner_firms.my_partner_firm(), default=str)
		for secret in (PAN, url, *phones.forms(PHONE)):
			self.assertNotIn(secret, own)
		self.assertTrue(partner_firms.my_partner_firm()["firm"]["has_pan"])
		self.assertTrue(partner_firms.my_partner_firm()["firm"]["phone_masked"].endswith(PHONE[-3:]))

	def test_no_other_role_reads_a_firm(self):
		code = self.ready_firm()
		for key in ("agent", "sales_manager", "client", "platform_admin", "basic"):
			_as(key)
			with self.subTest(key):
				self.assertFalse(frappe.has_permission(FIRM, "read", doc=code))
				with self.assertRaises(frappe.PermissionError):
					frappe.get_list(FIRM, pluck="name")
		_as("channel_partner")  # another partner, not this firm's contact
		self.assertFalse(frappe.has_permission(FIRM, "read", doc=code))
		self.assertEqual(frappe.get_list(FIRM, pluck="name"), [])

	def test_the_agreement_is_a_private_file_only_a_company_admin_opens(self):
		code = self.ready_firm()
		url = frappe.db.get_value(FIRM, code, "agreement")
		self.assertTrue(url.startswith("/private/files/"))
		file = frappe.get_doc("File", {"file_url": url})
		self.assertEqual((file.is_private, file.attached_to_doctype, file.attached_to_name), (1, FIRM, code))
		_as("company_admin")
		self.assertTrue(frappe.has_permission("File", "read", doc=file))
		# Not even the partner who uploaded it (the file's owner), nor any other role.
		for who in ("p701_one@example.com", "agent", "sales_manager", "channel_partner", "client"):
			_as(who)
			with self.subTest(who):
				self.assertFalse(frappe.has_permission("File", "read", doc=file))

	def test_another_file_is_not_touched_by_the_agreement_rule(self):
		self.assertIsNone(partner_firms.has_file_permission(frappe._dict(attached_to_doctype="Lead")))


class TestRegressionSeed(PartnerFirmCase):
	"""SOS-P7-01: the regression data is made through the production methods, and a run again changes nothing."""

	def setUp(self):
		super().setUp()
		self.addCleanup(self._remove_seeded_files)

	@staticmethod
	def _remove_seeded_files():
		for path in Path(frappe.get_site_path("private", "files")).glob("signed_agreement*"):
			path.unlink()

	def test_the_four_firms_are_seeded_each_in_its_own_status_and_a_second_run_adds_none(self):
		from sellos.tests import ui_fixtures

		admin = _email("company_admin")
		ui_fixtures._seed_partner_firms(admin)
		statuses = {
			row.firm_name: row.status
			for row in frappe.get_all(
				FIRM, filters={"firm_name": ["like", "Regression Firm %"]}, fields=["firm_name", "status"]
			)
		}
		self.assertEqual(
			statuses,
			{
				"Regression Firm Invited": "Invited",
				"Regression Firm Pending": "Pending approval",
				"Regression Firm Approved": "Approved",
				"Regression Firm Suspended": "Suspended",
			},
		)
		suspended = frappe.get_doc(FIRM, {"firm_name": "Regression Firm Suspended"})
		self.assertEqual(suspended.status_reason, "Regression: left the business")
		self.assertTrue(suspended.agreement.startswith("/private/files/"))
		self.assertEqual(suspended.pan, ui_fixtures.PARTNER_PAN)
		before = frappe.db.count(FIRM)
		ui_fixtures._seed_partner_firms(admin)
		self.assertEqual(frappe.db.count(FIRM), before)

	def test_the_gate_firm_fixture_and_its_cleanup(self):
		from sellos.tests import ui_fixtures

		# The fixtures commit for the browser's process. Here nothing is committed, so the test stays in its transaction.
		commit = patch.object(frappe.db, "commit")
		commit.start()
		self.addCleanup(commit.stop)
		made = ui_fixtures.seed_gate_partner_firm("pending")
		self.assertEqual(made["status"], "Pending approval")
		state = ui_fixtures.gate_partner_firm_state(made["name"])
		self.assertEqual(state["log"][1][:3], ("Invited", "Pending approval", _email("channel_partner")))
		self.assertEqual(ui_fixtures.seed_gate_partner_firm("pending"), made)  # safe to run again
		self.assertEqual(ui_fixtures.remove_gate_partner_firms(), {"firms": 1})
		self.assertFalse(frappe.db.exists(FIRM, made["name"]))
