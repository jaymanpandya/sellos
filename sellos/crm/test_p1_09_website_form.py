"""SOS-P1-09: the website lead endpoint. A per company key (only its hash is kept) opens the website
form's submit, a registered public intake method that calls the one intake function. A submission with
consent wording makes a lead and an inquiry Consent Record (Consented); one without is accepted, Unknown,
with a warning and no Consent Record; a bad key is refused; a flood is rate limited. Numbers come from
sellos.tests.phones; the keys are made by the code under test and the wording is the test's own."""

import hashlib
import json

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from sellos.access import intake_keys, public_intake
from sellos.crm import consent, website_form
from sellos.tests import phones

WORDING = "P109 test wording: I agree that the company may call me about properties."
SUBMIT = "sellos.crm.website_form.submit_website_lead"


def post(body, address):
	environ = EnvironBuilder(
		method="POST",
		path=f"/api/method/{SUBMIT}",
		base_url="https://tenant.example",
		data=json.dumps(body),
		content_type="application/json",
	)
	frappe.local.request = Request(environ.get_environ())
	frappe.local.request_ip = address
	frappe.local.response = frappe._dict()
	frappe.set_user("Guest")
	frappe.local.form_dict = frappe._dict(body)
	try:
		message = website_form.submit_website_lead()
	finally:
		frappe.set_user("Administrator")
	return message, frappe.local.response.get("http_status_code")


def counts():
	return {name: frappe.db.count(name) for name in ("Client", "Lead", "Consent Record", "Lead Activity")}


class WebsiteCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.key = intake_keys.make_key(intake_keys.LEAD_INTAKE, "P109 test", replace=True)
		# Each test has its own person and its own addresses (the rate counters live in the cache).
		seed = 9000 + int(hashlib.sha256(self.id().encode()).hexdigest()[:6], 16) % 900000
		self.person = phones.in_mobile(seed)
		self.address = self.new_address()

	def new_address(self):
		"""An address no earlier run has used (the rate counters live in the cache for two minutes)."""
		return f"198.51.{int(frappe.generate_hash(length=2), 16) % 250}.{int(frappe.generate_hash(length=2), 16) % 250}"

	def form(self, **extra):
		body = {"key": self.key, "name": "P109 Visitor", "phone": self.person, "consent_wording": WORDING}
		body.update(extra)
		return body

	def lead_of(self, number):
		client = frappe.db.get_value("Client", {"phone_key": number}, "name")
		return frappe.db.get_value(
			"Lead", {"client": client}, ["name", "source", "consent_status"], as_dict=True
		)


class TestValidSubmission(WebsiteCase):
	"""SOS-P1-09: a submission with consent wording."""

	def test_it_makes_a_consented_lead_and_a_consent_record_with_private_evidence(self):
		before = counts()
		message, status = post(self.form(message="Three bedrooms", form="Contact page"), self.address)
		self.assertIsNone(status)
		self.assertEqual(set(message), {"thank_you", "reference"})
		after = counts()
		self.assertEqual(after["Lead"], before["Lead"] + 1)
		self.assertEqual(after["Consent Record"], before["Consent Record"] + 1)
		lead = self.lead_of(self.person)
		self.assertEqual((lead.source, lead.consent_status), ("Website", consent.CONSENTED))
		record = frappe.get_all("Consent Record", {"lead": lead.name}, ["name", "basis", "evidence_link"])
		self.assertEqual([r.basis for r in record], ["Inquiry"])
		self.assertTrue(record[0].evidence_link.startswith("/private/files/"))
		file = frappe.get_doc("File", {"file_url": record[0].evidence_link})
		self.assertTrue(file.is_private)
		evidence = json.loads(file.get_content())
		self.assertEqual(evidence["wording"], WORDING)
		self.assertTrue(evidence["wording_version"])
		self.assertEqual(evidence["address"], self.address)
		self.assertEqual(evidence["page"], "Contact page")

	def test_a_known_person_is_merged_not_duplicated(self):
		post(self.form(), self.new_address())
		before = counts()
		post(self.form(name="P109 Visitor Again"), self.new_address())
		after = counts()
		self.assertEqual(after["Lead"], before["Lead"])
		self.assertEqual(after["Client"], before["Client"])
		self.assertEqual(after["Consent Record"], before["Consent Record"] + 1)


class TestBadKey(WebsiteCase):
	"""SOS-P1-09: a bad key is rejected and writes nothing."""

	def test_a_wrong_missing_or_other_scope_key_is_refused(self):
		listings = intake_keys.make_key(intake_keys.LISTINGS_READ, "P109 listings")
		before = counts()
		for key in ("not-the-key", "", None, listings):
			body = self.form()
			body["key"] = key
			message, status = post(body, self.new_address())
			self.assertEqual(status, 400, key)
			self.assertEqual(message, public_intake.BAD_FORM_ANSWER)
		self.assertEqual(counts(), before)

	def test_a_rotated_key_stops_working(self):
		old = self.key
		new = intake_keys.make_key(intake_keys.LEAD_INTAKE, "P109 new", replace=True)
		self.assertEqual(post(self.form(key=old), self.new_address())[1], 400)
		self.assertIsNone(post(self.form(key=new), self.new_address())[1])

	def test_only_the_hash_is_kept_and_no_key_is_listed(self):
		stored = frappe.get_all("Intake Key", fields=["key_hash"], pluck="key_hash")
		self.assertIn(intake_keys.hash_key(self.key), stored)
		self.assertNotIn(self.key, stored)
		self.assertNotIn(self.key, json.dumps(intake_keys.active_keys(intake_keys.LEAD_INTAKE), default=str))
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc("Intake Key", frappe.get_all("Intake Key", pluck="name")[0]).delete()


class TestMissingWording(WebsiteCase):
	"""SOS-P1-09: no consent wording is accepted, Unknown, with a warning and no Consent Record."""

	def test_the_lead_is_made_unknown_with_a_warning_and_no_consent_record(self):
		before = counts()
		body = self.form()
		del body["consent_wording"]
		message, status = post(body, self.new_address())
		self.assertIsNone(status)
		self.assertEqual(set(message), {"thank_you", "reference"})
		after = counts()
		self.assertEqual(after["Lead"], before["Lead"] + 1)
		self.assertEqual(after["Consent Record"], before["Consent Record"])
		lead = self.lead_of(self.person)
		self.assertEqual(lead.consent_status, consent.UNKNOWN)
		notes = frappe.get_all("Lead Activity", {"lead": lead.name}, pluck="notes")
		self.assertTrue(any(website_form.NO_WORDING_WARNING in (n or "") for n in notes), notes)


class TestFloodAndChecks(WebsiteCase):
	"""SOS-P1-09: the endpoint is rate limited, and the shared checks apply."""

	def test_a_flood_from_one_address_is_rate_limited_and_writes_nothing(self):
		address = self.address
		limit = website_form.PER_ADDRESS_PER_MINUTE
		statuses = []
		for _n in range(limit + 3):
			statuses.append(post({"key": "flood", "name": "x", "phone": self.person}, address)[1])
		self.assertEqual(statuses.count(429), 3)
		before = counts()
		message, status = post(self.form(), address)
		self.assertEqual((message, status), ("rate limited", 429))
		self.assertEqual(counts(), before)

	def test_a_filled_honeypot_and_an_unknown_field_write_nothing(self):
		before = counts()
		message, status = post(self.form(company_url="http://spam.example"), self.address)
		self.assertIsNone(status)
		self.assertEqual(set(message), {"thank_you", "reference"})
		self.assertEqual(post(self.form(surprise="x"), self.new_address())[1], 400)
		self.assertEqual(counts(), before)

	def test_it_is_a_registered_public_intake_with_the_scoped_key(self):
		checks = public_intake.declared_intakes()[SUBMIT]
		self.assertEqual(checks["calls_intake"], "sellos.crm.intake.take")
		self.assertIn("Lead intake", checks["form_key_setting"])
		self.assertEqual(checks["honeypot_field"], website_form.HONEYPOT)


class TestAdminMethods(WebsiteCase):
	"""SOS-P1-09: a Company Admin makes the key, sees it once and never again."""

	def test_the_key_is_returned_once_by_the_rotation_only(self):
		out = website_form.rotate_website_key()
		self.assertTrue(out["key"])
		self.assertTrue(intake_keys.key_valid(out["key"], intake_keys.LEAD_INTAKE))
		self.assertFalse(intake_keys.key_valid(self.key, intake_keys.LEAD_INTAKE))
		again = website_form.get_website_settings()
		self.assertNotIn("key", again)
		self.assertNotIn(out["key"], json.dumps(again, default=str))
		self.assertTrue(again["endpoint"].endswith(website_form.SUBMIT_PATH))
