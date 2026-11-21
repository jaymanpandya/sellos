"""SOS-P7-02: a partner of an approved firm registers a buyer, and the registration is protected."""

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from sellos.access import lead_permissions
from sellos.access import partner_registrations as pr
from sellos.access.roles import ensure_roles
from sellos.crm import consent, pipeline, site_visits
from sellos.crm.duplicates import normalise_phone
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

REG = "Partner Registration"
FIRM = "Channel Partner Firm"
OTHER_PARTNER = "p702_other_partner@example.com"


def visible(doctype):
	"""The names the signed in user can list, or [] when the role may not list the DocType at all."""
	try:
		return frappe.get_list(doctype, pluck="name")
	except frappe.PermissionError:
		return []


def _as(key):
	frappe.set_user(TEST_USERS[key]["email"] if key in TEST_USERS else key)


class PartnerRegistrationCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()
		pipeline.ensure_default_stages()
		from sellos.crm.lead_sources import ensure_default_sources

		ensure_default_sources()

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		self.seed = 0
		self.firm = self.make_firm(TEST_USERS["channel_partner"]["email"], "P702 Firm One")

	def make_firm(self, email, name, status="Approved"):
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "P702 Other",
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
				"contact_person": "P702 Contact",
				"email": email,
			}
		).insert(ignore_permissions=True)
		firm.db_set("status", status)
		return firm.name

	def buyer(self, **extra):
		"""Register a new buyer as the signed in partner. Each call uses a new phone number."""
		self.seed += 1
		values = {
			"buyer_name": f"P702 Buyer {self.seed}",
			"phone": phones.in_mobile(7100 + self.seed),
			**extra,
		}
		return pr.register_buyer(**values)

	def as_partner(self):
		_as("channel_partner")

	def registered(self, **extra):
		self.as_partner()
		result = self.buyer(**extra)
		frappe.set_user("Administrator")
		return result["registration"]["name"]


class TestRegistering(PartnerRegistrationCase):
	def test_a_new_buyer_makes_a_client_a_lead_and_a_registration_in_status_registered(self):
		self.as_partner()
		phone = phones.in_mobile(7001)
		result = pr.register_buyer(
			"P702 New Buyer",
			phone,
			project_of_interest="P702 Tower",
			note="Wants a 3 BHK",
			email="P702@Example.com",
		)
		self.assertTrue(result["accepted"])
		reg = frappe.get_doc(REG, result["registration"]["name"])
		self.assertEqual(reg.status, "Registered")
		self.assertEqual(reg.partner_firm, self.firm)
		self.assertEqual(reg.partner_user, TEST_USERS["channel_partner"]["email"])
		lead = frappe.get_doc("Lead", reg.lead)
		self.assertEqual(lead.source, "Channel partner")
		self.assertEqual(lead.partner, self.firm)
		self.assertEqual(lead.stage, pipeline.first_stage())
		self.assertEqual(lead.owner, TEST_USERS["channel_partner"]["email"])
		self.assertIn("P702 Tower", lead.notes)
		client = frappe.get_doc("Client", reg.client)
		self.assertEqual(client.phone, normalise_phone(phone))
		self.assertEqual(client.email, "p702@example.com")
		self.assertEqual([row.to_status for row in reg.status_log], ["Registered"])
		self.assertEqual(reg.consent_wording, pr.DEFAULT_WORDING)

	def test_the_partner_sees_the_phone_masked_never_in_full(self):
		self.as_partner()
		phone = phones.in_mobile(7002)
		result = pr.register_buyer("P702 Masked Buyer", phone)
		text = json.dumps(result, default=str)
		for form in phones.forms(phone):
			self.assertNotIn(form, text)
		self.assertTrue(result["registration"]["phone_masked"].endswith(phone[-3:]))
		mine = json.dumps(pr.my_partner_registrations(), default=str)
		for form in phones.forms(phone):
			self.assertNotIn(form, mine)

	def test_without_the_partners_confirmation_consent_is_unknown_with_a_warning(self):
		self.as_partner()
		result = self.buyer()["registration"]
		self.assertEqual(result["consent"]["status"], consent.UNKNOWN)
		self.assertEqual(result["consent"]["warning"], "amber")
		self.assertFalse(frappe.db.exists("Consent Record", {"lead": result["lead"]}))

	def test_when_the_partner_confirms_the_buyer_agreed_a_consent_record_is_made(self):
		self.as_partner()
		result = self.buyer(buyer_agreed=1)["registration"]
		self.assertEqual(result["consent"]["status"], consent.CONSENTED)
		record = frappe.get_all(
			"Consent Record", filters={"lead": result["lead"]}, fields=["basis", "evidence_link"]
		)
		self.assertEqual(len(record), 1)
		self.assertEqual(record[0].basis, "Consent")
		self.assertIn(result["name"], record[0].evidence_link)
		self.assertEqual(frappe.db.get_value(REG, result["name"], "buyer_agreed"), 1)

	def test_the_consent_wording_shown_is_the_company_setting_and_is_kept(self):
		_as("company_admin")
		pr.save_partner_settings(consent_wording="P702 I agree to be called.")
		self.as_partner()
		self.assertEqual(pr.partner_registration_form()["consent_wording"], "P702 I agree to be called.")
		name = self.buyer(buyer_agreed=1)["registration"]["name"]
		self.assertEqual(frappe.db.get_value(REG, name, "consent_wording"), "P702 I agree to be called.")

	def test_consent_never_blocks_a_registration(self):
		self.as_partner()
		self.assertTrue(self.buyer(buyer_agreed=0)["accepted"])

	def test_a_name_and_a_phone_are_needed_and_the_email_is_checked(self):
		self.as_partner()
		with self.assertRaises(frappe.ValidationError):
			pr.register_buyer("", phones.in_mobile(7003))
		with self.assertRaises(frappe.ValidationError):
			pr.register_buyer("P702 No Phone", "")
		with self.assertRaises(frappe.ValidationError):
			pr.register_buyer("P702 Bad Email", phones.in_mobile(7004), email="not an email")


class TestExistingBuyer(PartnerRegistrationCase):
	def existing(self, **fields):
		_as("company_admin")
		client = frappe.get_doc(
			{"doctype": "Client", "client_name": "P702 Existing Buyer", "client_type": "Buyer", **fields}
		).insert()
		lead = frappe.get_doc({"doctype": "Lead", "client": client.name, "source": "Website"}).insert()
		self.as_partner()
		return client, lead

	def test_an_existing_buyer_by_phone_makes_no_second_lead_and_the_reply_is_only_the_sentence(self):
		phone = phones.in_mobile(7010)
		_client, lead = self.existing(phone=phone)
		before = frappe.db.count("Lead")
		result = pr.register_buyer("Somebody Else", phone)
		self.assertEqual(result, {"accepted": False, "message": pr.NOT_ACCEPTED})
		self.assertEqual(pr.NOT_ACCEPTED, "Not accepted: this buyer is already registered with the company.")
		self.assertEqual(frappe.db.count("Lead"), before)
		self.assertFalse(frappe.db.exists(REG, {"lead": lead.name}))

	def test_an_existing_buyer_by_email_is_not_accepted_and_nothing_about_them_leaks(self):
		client, lead = self.existing(email="p702_existing@example.com")
		result = pr.register_buyer("Other Name", phones.in_mobile(7011), email="p702_existing@example.com")
		text = json.dumps(result)
		self.assertEqual(result["message"], pr.NOT_ACCEPTED)
		for secret in (client.name, lead.name, client.client_name, lead.stage, "p702_existing"):
			self.assertNotIn(secret, text)

	def test_an_existing_buyer_who_another_partner_registered_gets_the_same_reply(self):
		self.as_partner()
		phone = phones.in_mobile(7012)
		self.assertTrue(pr.register_buyer("P702 First", phone)["accepted"])
		other = self.make_firm(OTHER_PARTNER, "P702 Firm Two")
		self.assertTrue(other)
		_as(OTHER_PARTNER)
		self.assertEqual(
			pr.register_buyer("P702 Second", phone), {"accepted": False, "message": pr.NOT_ACCEPTED}
		)


class TestRateLimit(PartnerRegistrationCase):
	def test_the_default_limit_is_twenty_and_the_next_registration_in_an_hour_is_refused(self):
		self.assertEqual(pr.lead_limit(), 20)
		self.as_partner()
		now = now_datetime()
		for _n in range(20):
			pr._note_attempt(frappe.session.user, self.firm, "Registered", now)
		with self.assertRaises(frappe.TooManyRequestsError) as caught:
			self.buyer()
		self.assertIn("20", str(caught.exception))
		self.assertEqual(frappe.db.count("Partner Registration"), 0)

	def test_the_next_hour_lets_the_partner_register_again(self):
		self.as_partner()
		start = now_datetime()
		for _n in range(20):
			pr._note_attempt(frappe.session.user, self.firm, "Registered", start)
		self.seed += 1
		with self.assertRaises(frappe.TooManyRequestsError):
			pr.register("P702 Early", phones.in_mobile(7200), on=add_to_date(start, minutes=59))
		result = pr.register("P702 Later", phones.in_mobile(7200), on=add_to_date(start, minutes=61))
		self.assertTrue(result["accepted"])

	def test_the_limit_is_the_company_setting_and_a_real_run_hits_it(self):
		_as("company_admin")
		pr.save_partner_settings(partner_lead_limit=2)
		self.as_partner()
		self.assertEqual(pr.partner_registration_form()["remaining"], 2)
		self.buyer()
		self.buyer()
		with self.assertRaises(frappe.TooManyRequestsError):
			self.buyer()
		self.assertEqual(pr.partner_registration_form()["remaining"], 0)

	def test_a_refused_try_counts_so_the_limit_stops_probing(self):
		_as("company_admin")
		pr.save_partner_settings(partner_lead_limit=2)
		phone = phones.in_mobile(7201)
		frappe.get_doc(
			{"doctype": "Client", "client_name": "P702 Known", "client_type": "Buyer", "phone": phone}
		).insert()
		self.as_partner()
		self.assertFalse(pr.register_buyer("A", phone)["accepted"])
		self.assertFalse(pr.register_buyer("B", phone)["accepted"])
		with self.assertRaises(frappe.TooManyRequestsError):
			pr.register_buyer("C", phone)

	def test_one_partners_limit_is_not_anothers(self):
		_as("company_admin")
		pr.save_partner_settings(partner_lead_limit=1)
		self.make_firm(OTHER_PARTNER, "P702 Firm Two")
		self.as_partner()
		self.buyer()
		_as(OTHER_PARTNER)
		self.assertTrue(self.buyer()["accepted"])


class TestDecision(PartnerRegistrationCase):
	def test_approval_protects_the_registration_for_ninety_days_from_the_approval(self):
		name = self.registered()
		_as("company_admin")
		before = now_datetime()
		pr.approve_partner_registration(name)
		doc = frappe.get_doc(REG, name)
		self.assertEqual(doc.status, "Approved")
		self.assertEqual(doc.decided_by, TEST_USERS["company_admin"]["email"])
		self.assertGreaterEqual(get_datetime(doc.approved_on), before.replace(microsecond=0))
		days = (get_datetime(doc.protected_until) - get_datetime(doc.approved_on)).days
		self.assertEqual(days, 90)
		self.assertTrue(pr.is_protected(doc.lead))
		self.assertEqual([row.to_status for row in doc.status_log], ["Registered", "Approved"])
		self.assertEqual(doc.status_log[1].changed_by, TEST_USERS["company_admin"]["email"])

	def test_the_protection_days_are_the_company_setting(self):
		_as("company_admin")
		pr.save_partner_settings(partner_protection_days=30)
		self.as_partner()
		name = self.buyer()["registration"]["name"]
		_as("company_admin")
		pr.approve_partner_registration(name)
		doc = frappe.get_doc(REG, name)
		self.assertEqual((get_datetime(doc.protected_until) - get_datetime(doc.approved_on)).days, 30)

	def test_a_rejection_needs_a_reason_and_the_partner_sees_it(self):
		name = self.registered()
		_as("company_admin")
		with self.assertRaises(frappe.ValidationError):
			pr.reject_partner_registration(name, "  ")
		pr.reject_partner_registration(name, "Already a customer elsewhere")
		doc = frappe.get_doc(REG, name)
		self.assertEqual((doc.status, doc.rejection_reason), ("Rejected", "Already a customer elsewhere"))
		self.assertFalse(pr.is_protected(doc.lead))
		self.as_partner()
		mine = pr.my_partner_registrations()["registrations"][0]
		self.assertEqual(mine["status"], "Rejected")
		self.assertEqual(mine["rejection_reason"], "Already a customer elsewhere")

	def test_only_a_registered_registration_is_decided_once(self):
		name = self.registered()
		_as("company_admin")
		pr.approve_partner_registration(name)
		with self.assertRaises(frappe.ValidationError):
			pr.approve_partner_registration(name)
		with self.assertRaises(frappe.ValidationError):
			pr.reject_partner_registration(name, "late")

	def test_only_a_company_admin_decides(self):
		name = self.registered()
		for key in ("agent", "channel_partner", "sales_manager", "client", "platform_admin"):
			_as(key)
			with self.subTest(key), self.assertRaises(frappe.PermissionError):
				pr.approve_partner_registration(name)
			with self.subTest(key), self.assertRaises(frappe.PermissionError):
				pr.reject_partner_registration(name, "no")

	def test_a_status_is_never_set_by_hand(self):
		name = self.registered()
		_as("company_admin")
		doc = frappe.get_doc(REG, name)
		doc.status = "Approved"
		with self.assertRaises(frappe.PermissionError):
			doc.save()


class TestFollowingTheLead(PartnerRegistrationCase):
	def approved(self):
		name = self.registered()
		_as("company_admin")
		pr.approve_partner_registration(name)
		return name, frappe.db.get_value(REG, name, "lead")

	def test_a_site_visit_marked_done_moves_the_registration_to_visited(self):
		name, lead = self.approved()
		visit = frappe.get_doc(
			{
				"doctype": "Site Visit",
				"lead": lead,
				"project_name": "P702 Tower",
				"visit_datetime": now_datetime(),
			}
		).insert()
		self.assertEqual(frappe.db.get_value(REG, name, "status"), "Approved")
		site_visits.complete(visit.name, "Liked it")
		self.assertEqual(frappe.db.get_value(REG, name, "status"), "Visited")
		doc = frappe.get_doc(REG, name)
		self.assertEqual([row.to_status for row in doc.status_log], ["Registered", "Approved", "Visited"])
		self.assertTrue(pr.is_protected(lead))

	def test_a_done_visit_before_approval_leaves_the_registration_registered(self):
		name = self.registered()
		lead = frappe.db.get_value(REG, name, "lead")
		visit = frappe.get_doc(
			{
				"doctype": "Site Visit",
				"lead": lead,
				"project_name": "P702 Tower",
				"visit_datetime": now_datetime(),
			}
		).insert()
		site_visits.complete(visit.name, "Liked it")
		self.assertEqual(frappe.db.get_value(REG, name, "status"), "Registered")

	def test_a_booking_moves_it_to_booked_and_a_booked_one_never_expires(self):
		name, lead = self.approved()
		self.assertTrue(pr.mark_booked(lead))
		self.assertEqual(frappe.db.get_value(REG, name, "status"), "Booked")
		far = add_to_date(now_datetime(), days=400)
		self.assertEqual(pr.expire_registrations(far), [])
		self.assertEqual(frappe.db.get_value(REG, name, "status"), "Booked")
		self.assertTrue(pr.is_protected(lead, far))

	def test_a_protected_registration_whose_window_ends_without_a_booking_expires_with_a_fixed_clock(self):
		name, lead = self.approved()
		until = get_datetime(frappe.db.get_value(REG, name, "protected_until"))
		self.assertEqual(pr.expire_registrations(add_to_date(until, seconds=-1)), [])
		self.assertEqual(frappe.db.get_value(REG, name, "status"), "Approved")
		self.assertEqual(pr.expire_registrations(add_to_date(until, seconds=1)), [name])
		doc = frappe.get_doc(REG, name)
		self.assertEqual(doc.status, "Expired")
		self.assertEqual(doc.status_log[-1].to_status, "Expired")
		self.assertFalse(pr.is_protected(lead, add_to_date(until, seconds=1)))
		self.assertEqual(pr.expire_registrations(add_to_date(until, days=1)), [])  # again: nothing changes

	def test_a_visited_registration_expires_too_and_a_registered_one_never_does(self):
		name, lead = self.approved()
		pr.mark_visited(lead)
		waiting = self.registered()
		until = get_datetime(frappe.db.get_value(REG, name, "protected_until"))
		self.assertEqual(pr.expire_registrations(add_to_date(until, days=1)), [name])
		self.assertEqual(frappe.db.get_value(REG, waiting, "status"), "Registered")


class TestProtectionAndThePartnerChange(PartnerRegistrationCase):
	def setUp(self):
		super().setUp()
		name = self.registered()
		_as("company_admin")
		pr.approve_partner_registration(name)
		self.name = name
		self.lead = frappe.db.get_value(REG, name, "lead")
		self.other = self.make_firm(OTHER_PARTNER, "P702 Firm Two")

	def test_nobody_but_a_company_admin_changes_the_partner_of_a_protected_lead(self):
		self.assertTrue(pr.is_protected(self.lead))
		for key in ("agent", "channel_partner", "sales_manager", "platform_admin", "client"):
			_as(key)
			with self.subTest(key), self.assertRaises(frappe.PermissionError):
				pr.change_lead_partner(self.lead, self.other)
		for key in ("agent", "sales_manager"):
			_as("company_admin")
			doc = frappe.get_doc("Lead", self.lead)
			doc.assigned_to = TEST_USERS["agent"]["email"]
			doc.save()
			_as(key)
			doc = frappe.get_doc("Lead", self.lead)
			doc.partner = self.other
			with self.subTest(key), self.assertRaises(frappe.PermissionError):
				doc.save()
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "partner"), self.firm)

	def test_a_company_admin_changes_it_and_the_change_is_logged(self):
		_as("company_admin")
		pr.change_lead_partner(self.lead, self.other)
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "partner"), self.other)
		log = frappe.get_doc(REG, self.name).status_log[-1]
		self.assertEqual((log.from_status, log.to_status), ("Approved", "Approved"))
		self.assertIn("P702", log.note.replace(self.firm, "P702").replace(self.other, "P702"))
		self.assertIn(self.firm, log.note)
		self.assertIn(self.other, log.note)
		self.assertIn(TEST_USERS["company_admin"]["email"], log.note)
		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Lead", "reference_name": self.lead, "comment_type": "Info"},
			pluck="content",
		)
		self.assertTrue(any(self.other in text for text in comments))

	def test_protection_never_blocks_an_agents_work_a_call_or_a_message(self):
		_as("company_admin")
		frappe.db.set_value("Lead", self.lead, "assigned_to", TEST_USERS["agent"]["email"])
		_as("agent")
		doc = frappe.get_doc("Lead", self.lead)
		doc.notes = "P702 the agent works the lead"
		doc.save()
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "notes"), "P702 the agent works the lead")
		check = consent.check_contact(self.lead, "Call")
		self.assertFalse(check.refused)


class TestPermissions(PartnerRegistrationCase):
	def test_a_partner_sees_only_their_own_registrations(self):
		mine = self.registered()
		self.make_firm(OTHER_PARTNER, "P702 Firm Two")
		_as(OTHER_PARTNER)
		theirs = self.buyer()["registration"]["name"]
		self.assertEqual([r["name"] for r in pr.my_partner_registrations()["registrations"]], [theirs])
		self.assertEqual(frappe.get_list(REG, pluck="name"), [theirs])
		self.assertFalse(frappe.has_permission(REG, "read", doc=mine))
		self.as_partner()
		self.assertEqual(frappe.get_list(REG, pluck="name"), [mine])
		self.assertTrue(frappe.has_permission(REG, "read", doc=mine))

	def test_a_partner_reads_their_lead_and_changes_nothing_after_registering(self):
		name = self.registered()
		lead = frappe.db.get_value(REG, name, "lead")
		self.as_partner()
		self.assertTrue(frappe.has_permission("Lead", "read", doc=lead))
		for ptype in ("write", "delete", "create"):
			self.assertFalse(frappe.has_permission("Lead", ptype, doc=lead), ptype)
			self.assertFalse(frappe.has_permission(REG, ptype, doc=name), ptype)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Lead", lead).check_permission("write")
		activity = frappe.new_doc("Lead Activity")
		activity.lead = lead
		self.assertFalse(frappe.has_permission("Lead Activity", "create", doc=activity))
		self.assertEqual(frappe.get_list("Lead", pluck="name"), [lead])

	def test_a_partner_cannot_make_a_lead_any_other_way(self):
		self.as_partner()
		lead = frappe.new_doc("Lead")
		self.assertFalse(frappe.has_permission("Lead", "create", doc=lead))
		with self.assertRaises(frappe.PermissionError):
			lead.check_permission("create")

	def test_no_other_role_reads_a_registration(self):
		name = self.registered()
		for key in ("agent", "sales_manager", "client", "platform_admin"):
			_as(key)
			with self.subTest(key):
				self.assertEqual(visible(REG), [])
				self.assertFalse(frappe.has_permission(REG, "read", doc=name))
		_as("company_admin")
		self.assertEqual(frappe.get_list(REG, pluck="name"), [name])

	def test_only_a_partner_of_an_approved_firm_registers(self):
		for status in ("Invited", "Pending approval", "Suspended"):
			frappe.db.set_value(FIRM, self.firm, "status", status)
			self.as_partner()
			with self.subTest(status), self.assertRaises(frappe.PermissionError):
				self.buyer()
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.count(REG), 0)
		for key in ("agent", "company_admin", "sales_manager", "client"):
			_as(key)
			with self.subTest(key), self.assertRaises(frappe.PermissionError):
				self.buyer()

	def test_a_partner_with_no_firm_cannot_register(self):
		frappe.db.set_value(FIRM, self.firm, "contact_user", TEST_USERS["agent"]["email"])
		self.as_partner()
		with self.assertRaises(frappe.PermissionError):
			self.buyer()

	def test_the_company_admin_sees_the_full_phone_and_the_partner_does_not(self):
		self.as_partner()
		phone = phones.in_mobile(7300)
		pr.register_buyer("P702 Full", phone)
		_as("company_admin")
		listed = pr.list_partner_registrations()
		self.assertEqual(listed["registrations"][0]["phone"], normalise_phone(phone))
		self.assertEqual(listed["counts"]["Registered"], 1)

	def test_only_a_company_admin_reads_and_saves_the_settings(self):
		_as("company_admin")
		self.assertEqual(pr.get_partner_settings()["partner_protection_days"], 90)
		with self.assertRaises(frappe.ValidationError):
			pr.save_partner_settings(partner_lead_limit=0)
		for key in ("agent", "channel_partner", "sales_manager", "client", "platform_admin"):
			_as(key)
			with self.subTest(key), self.assertRaises(frappe.PermissionError):
				pr.get_partner_settings()

	def test_the_expiry_runs_on_the_hourly_scheduler(self):
		hooks = frappe.get_hooks("scheduler_events")
		self.assertIn("sellos.access.partner_registrations.expire_registrations", hooks["hourly"])

	def test_the_lead_permission_scope_of_a_partner_stays_own(self):
		self.assertEqual(lead_permissions.scope_for(["SellOS Channel Partner"]), "own")


class TestFixtures(PartnerRegistrationCase):
	"""SOS-P7-02: the regression data and the browser spec's fixtures, read back."""

	def setUp(self):
		from pathlib import Path
		from unittest.mock import patch

		super().setUp()
		# The fixtures commit for the browser's process. Here nothing is committed.
		commit = patch.object(frappe.db, "commit")
		commit.start()
		self.addCleanup(commit.stop)
		self.addCleanup(self._remove_files, Path)

	@staticmethod
	def _remove_files(path_class):
		for pattern in ("signed_agreement*", "gate_agreement*"):
			for path in path_class(frappe.get_site_path("private", "files")).glob(pattern):
				path.unlink()

	def test_the_regression_registrations_are_seeded_once_each_in_its_own_status(self):
		from sellos.tests import ui_fixtures

		admin = TEST_USERS["company_admin"]["email"]
		ui_fixtures._seed_partner_firms(admin)
		ui_fixtures._seed_partner_registrations(admin)
		statuses = {
			row.buyer_name: row.status
			for row in frappe.get_all(
				REG,
				filters={"buyer_name": ["like", "Regression Partner Buyer %"]},
				fields=["buyer_name", "status"],
			)
		}
		self.assertEqual(
			statuses,
			{
				"Regression Partner Buyer One": "Registered",
				"Regression Partner Buyer Two": "Approved",
				"Regression Partner Buyer Three": "Rejected",
			},
		)
		two = frappe.get_doc(REG, {"buyer_name": "Regression Partner Buyer Two"})
		self.assertTrue(two.protected_until)
		self.assertEqual(frappe.db.get_value("Lead", two.lead, "consent_status"), consent.CONSENTED)
		before = frappe.db.count(REG)
		ui_fixtures._seed_partner_registrations(admin)
		self.assertEqual(frappe.db.count(REG), before)

	def test_the_gate_fixtures_make_an_approved_firm_a_known_buyer_and_clean_up(self):
		from sellos.tests import ui_fixtures

		made = ui_fixtures.seed_gate_partner_firm("approved")
		self.assertEqual(made["status"], "Approved")
		buyer = ui_fixtures.seed_gate_partner_buyer()
		self.assertEqual(ui_fixtures.count_gate_partner_leads(), {"leads": 1, "registrations": 0})
		_as("channel_partner")
		self.assertEqual(
			pr.register_buyer("Somebody", buyer["existing_phone"]),
			{"accepted": False, "message": pr.NOT_ACCEPTED},
		)
		name = f"{ui_fixtures.GATE_BUYER_PREFIX}New"
		self.assertTrue(pr.register_buyer(name, buyer["new_phone"], buyer_agreed=1)["accepted"])
		state = ui_fixtures.gate_partner_registration_state(name)
		self.assertEqual(
			(state["status"], state["lead_partner"], state["lead_source"]),
			("Registered", made["name"], "Channel partner"),
		)
		self.assertEqual((state["consent_status"], state["count"]), (consent.CONSENTED, 1))
		frappe.set_user("Administrator")
		removed = ui_fixtures.remove_gate_partner_registrations()
		self.assertEqual(removed, {"registrations": 1, "leads": 2, "clients": 2})
		self.assertEqual(ui_fixtures.count_gate_partner_leads(), {"leads": 0, "registrations": 0})
