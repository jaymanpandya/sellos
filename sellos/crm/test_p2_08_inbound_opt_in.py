"""SOS-P2-08: the inbound opt in route. A missed call to the 022 number (a Plivo shaped event through the
signed webhook) and the enquiry page (the first public intake method) both reach the one intake function,
sellos.crm.intake.take. A known lead keeps its stage and becomes Consented with an inquiry Consent Record
for 7 days; an unknown number is a new lead on the New stage; a stop request is Opted out with a red
warning and never blocks. Numbers come from sellos.tests.phones; the signing key and form key are fake."""

import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_datetime
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from sellos.access import public_intake
from sellos.crm import consent, enquiry, intake, pipeline
from sellos.telephony import inbound
from sellos.telephony.queue import caller_queue
from sellos.telephony.test_p2_06_webhook import LANDLINE, WebhookCase, call_endpoint
from sellos.tests import phones

CALLER = phones.in_mobile(3801)
STRANGER = phones.in_mobile(3802)
FORM_PERSON = phones.in_mobile(3803)
ADDRESS = "203.0.113.58"
WORDING = "P208 test wording: I agree to be called back about properties."
SUBMIT = "sellos.crm.enquiry.submit_enquiry"


def counts():
	return {name: frappe.db.count(name) for name in ("Client", "Lead", "Consent Record", "Lead Activity")}


def evidence_of(record) -> dict:
	url = frappe.db.get_value("Consent Record", record, "evidence_link")
	file = frappe.get_doc("File", {"file_url": url})
	assert file.is_private and url.startswith("/private/files/"), url
	return json.loads(file.get_content())


class InboundCase(WebhookCase):
	"""A Company Admin site with the 022 number saved, a known lead and the fake signing key."""

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("SellOS Settings", "consent_wording", WORDING)
		frappe.db.set_single_value("SellOS Settings", "consent_enforcement", 0)
		self.call_no = 0

	def known_lead(self, number=CALLER):
		"""The setUp lead, with its client given this number (saved, so its match key is set too)."""
		client = frappe.get_doc("Client", frappe.db.get_value("Lead", self.lead, "client"))
		client.phone = number
		client.flags.ignore_permissions = True
		client.save()
		return self.lead

	def missed_call(
		self, number, status="no-answer", duration="0", direction="inbound", to=None, call_id=None
	):
		self.call_no += 1
		params = {
			"CallUUID": call_id or f"p208-call-{self.call_no}-{frappe.generate_hash(length=6)}",
			"CallStatus": status,
			"Direction": direction,
			"From": number,
			"To": to or LANDLINE,
			"Duration": duration,
		}
		return params, call_endpoint(
			params, nonce=f"p208-nonce-{self.call_no}-{frappe.generate_hash(length=6)}"
		)


class TestMissedCall(InboundCase):
	"""SOS-P2-08: a missed call is detected without being answered."""

	def test_a_missed_call_from_a_known_lead_changes_no_stage_and_makes_the_lead_consented(self):
		lead = self.known_lead()
		stage = frappe.db.get_value("Lead", lead, "stage")
		self.assertEqual(consent.compute_status(lead), consent.UNKNOWN)
		before = counts()
		params, (message, status) = self.missed_call(CALLER)
		self.assertEqual((message, status), ("ok", None))
		after = counts()
		self.assertEqual(after["Lead"], before["Lead"])
		self.assertEqual(after["Client"], before["Client"])
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), stage)
		self.assertEqual(frappe.db.get_value("Lead", lead, "consent_status"), consent.CONSENTED)
		record = frappe.get_all(
			"Consent Record", {"lead": lead, "basis": "Inquiry"}, ["name", "recorded_on", "expires_on"]
		)
		self.assertEqual(len(record), 1)
		days = (get_datetime(record[0].expires_on) - get_datetime(record[0].recorded_on)).days
		self.assertEqual(days, 7)
		evidence = evidence_of(record[0].name)
		self.assertEqual(evidence["call_id"], params["CallUUID"])
		activity = frappe.get_all("Lead Activity", {"lead": lead, "activity_type": "Call"}, ["notes"])
		self.assertEqual(len(activity), 1)
		self.assertIn("Missed call", activity[0].notes)

	def test_the_lead_rises_in_the_caller_queue(self):
		lead = self.known_lead()
		_, other = self.make_lead()  # a second lead with no consent record, made later
		frappe.set_user("Administrator")
		before = {row["lead"]: row for row in caller_queue()}
		self.assertEqual(before[lead]["consent_status"], consent.UNKNOWN)
		self.missed_call(CALLER)
		rows = {row["lead"]: row for row in caller_queue()}
		self.assertEqual(rows[lead]["consent_status"], consent.CONSENTED)
		self.assertLess(rows[lead]["position"], rows[other]["position"])
		self.assertTrue(rows[lead]["time_left"])

	def test_a_missed_call_from_an_unknown_number_makes_a_lead_on_the_new_stage(self):
		before = counts()
		self.missed_call(STRANGER)
		after = counts()
		self.assertEqual(after["Lead"], before["Lead"] + 1)
		self.assertEqual(after["Client"], before["Client"] + 1)
		self.assertEqual(after["Consent Record"], before["Consent Record"] + 1)
		self.assertEqual(after["Lead Activity"], before["Lead Activity"] + 1)
		client = frappe.db.get_value("Client", {"phone_key": STRANGER}, "name")
		lead = frappe.db.get_value(
			"Lead", {"client": client}, ["name", "source", "stage", "consent_status"], as_dict=True
		)
		self.assertEqual(lead.source, "Missed call")
		self.assertEqual(lead.stage, pipeline.first_stage())
		self.assertEqual(lead.consent_status, consent.CONSENTED)
		self.assertNotIn(STRANGER[-6:], frappe.db.get_value("Client", client, "client_name"))

	def test_the_same_call_reported_twice_and_a_replay_change_nothing(self):
		params, _ = self.missed_call(STRANGER, call_id="p208-same-call")
		first = counts()
		call_endpoint(params, nonce="p208-another-nonce")  # the same call, a new nonce
		self.assertEqual(counts(), first)
		replay = call_endpoint(params, nonce="p208-replayed")
		call_endpoint(params, nonce="p208-replayed")
		self.assertEqual(counts(), first)
		self.assertEqual(replay[1], None)

	def test_what_is_not_a_missed_call_writes_nothing(self):
		before = counts()
		self.missed_call(STRANGER, duration="42")  # talked
		self.missed_call(STRANGER, status="ringing")  # not over yet
		self.missed_call(STRANGER, direction="outbound")  # our own call
		self.missed_call(STRANGER, to=phones.in_mobile(3899))  # not the 022 number
		self.assertEqual(counts(), before)

	def test_a_missed_call_with_no_saved_022_number_writes_nothing(self):
		frappe.db.set_single_value("Telephony Settings", "phone_number", "")
		before = counts()
		self.assertFalse(inbound.our_number())
		self.missed_call(STRANGER)
		self.assertEqual(counts(), before)

	def test_a_bad_signature_writes_nothing(self):
		before = counts()
		params = {
			"CallUUID": "p208-unsigned",
			"CallStatus": "no-answer",
			"Direction": "inbound",
			"From": STRANGER,
			"To": LANDLINE,
		}
		message, status = call_endpoint(params, nonce="p208-bad", signature="not-the-signature")
		self.assertEqual((message, status), ("refused", 403))
		self.assertEqual(counts(), before)

	def test_a_missed_call_from_an_opted_out_lead_is_recorded_and_stays_opted_out(self):
		lead = self.known_lead()
		consent.record_opt_out(lead, "Phone call")
		self.missed_call(CALLER)
		self.assertEqual(consent.compute_status(lead), consent.OPTED_OUT)
		self.assertEqual(len(frappe.get_all("Consent Record", {"lead": lead})), 1)


def submit(body, address=ADDRESS, extra_length=0):
	"""Call the enquiry submit method as a guest, with a built JSON request."""
	raw = json.dumps(body)
	environ = EnvironBuilder(
		method="POST",
		path=f"/api/method/{SUBMIT}",
		base_url="https://tenant.example",
		data=raw + " " * extra_length,
		content_type="application/json",
	)
	frappe.local.request = Request(environ.get_environ())
	frappe.local.request_ip = address
	frappe.local.response = frappe._dict()
	frappe.set_user("Guest")  # set_user clears the form, so the form is set after it
	frappe.local.form_dict = frappe._dict(body)
	try:
		message = enquiry.submit_enquiry()
	finally:
		frappe.set_user("Administrator")
	return message, frappe.local.response.get("http_status_code")


class EnquiryCase(InboundCase):
	def setUp(self):
		super().setUp()
		self.key = public_intake.form_key()
		frappe.cache.delete_keys("sellos_intake_rate")
		frappe.cache.delete_keys("sellos_webhook_rate")

	def form(self, **extra):
		body = {"key": self.key, "name": "P208 Person", "phone": FORM_PERSON, "website": "", "stop": "0"}
		body.update(extra)
		return body


class TestEnquiryPage(EnquiryCase):
	"""SOS-P2-08: the enquiry page records the consent wording and makes or merges the lead."""

	def test_a_new_person_gets_a_lead_a_consent_record_and_the_wording_as_evidence(self):
		before = counts()
		message, status = submit(self.form(email="p208@example.com", message="Two bedrooms in Powai"))
		self.assertIsNone(status)
		self.assertEqual(set(message), {"thank_you", "reference"})
		after = counts()
		self.assertEqual(after["Lead"], before["Lead"] + 1)
		client = frappe.db.get_value("Client", {"phone_key": FORM_PERSON}, "name")
		lead = frappe.db.get_value(
			"Lead", {"client": client}, ["name", "source", "stage", "consent_status"], as_dict=True
		)
		self.assertEqual((lead.source, lead.stage), ("Website", pipeline.first_stage()))
		self.assertEqual(lead.consent_status, consent.CONSENTED)
		record = frappe.get_all(
			"Consent Record", {"lead": lead.name}, ["name", "basis", "recorded_on", "expires_on"]
		)
		self.assertEqual([r.basis for r in record], ["Inquiry"])
		self.assertEqual((get_datetime(record[0].expires_on) - get_datetime(record[0].recorded_on)).days, 7)
		evidence = evidence_of(record[0].name)
		self.assertEqual(evidence["wording"], WORDING)
		self.assertEqual(evidence["wording_version"], enquiry.wording_version(WORDING))
		self.assertEqual(evidence["address"], ADDRESS)
		self.assertEqual(evidence["submitted"]["message"], "Two bedrooms in Powai")
		self.assertTrue(evidence["shown_and_submitted_on"])
		self.assertIn(
			message["reference"], frappe.db.get_value("Consent Record", record[0].name, "evidence_link")
		)

	def test_a_new_wording_has_a_new_version(self):
		self.assertNotEqual(enquiry.wording_version(WORDING), enquiry.wording_version(WORDING + " More."))

	def test_a_known_person_keeps_their_lead_and_stage(self):
		self.known_lead(FORM_PERSON)
		stage = frappe.db.get_value("Lead", self.lead, "stage")
		before = counts()
		submit(self.form())
		after = counts()
		self.assertEqual((after["Lead"], after["Client"]), (before["Lead"], before["Client"]))
		self.assertEqual(after["Consent Record"], before["Consent Record"] + 1)
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "stage"), stage)
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "consent_status"), consent.CONSENTED)

	def test_the_answer_is_the_same_for_a_new_and_a_known_person(self):
		new, _ = submit(self.form())
		known, _ = submit(self.form())
		self.assertEqual(set(new), set(known))
		self.assertNotEqual(new["reference"], known["reference"])

	def test_the_page_shows_the_wording_and_reads_no_record(self):
		from sellos.www import enquiry as page

		context = frappe._dict()
		with patch.object(page.frappe, "form_dict", frappe._dict(k=self.key)):
			page.get_context(context)
		self.assertEqual(context.consent_wording, WORDING)
		self.assertEqual(context.key, self.key)
		html = (Path(page.__file__).parent / "enquiry.html").read_text(encoding="utf-8")
		self.assertIn("consent_wording", html)
		self.assertNotIn("Frappe", html)


class TestStopRequest(EnquiryCase):
	"""SOS-P2-08: a stop request is Opted out with a red warning and never blocks."""

	def test_a_stop_from_the_form_is_opted_out_with_a_red_warning_and_no_inquiry(self):
		self.known_lead(FORM_PERSON)
		submit(self.form(stop="1"))
		view = consent.consent_view(self.lead)
		self.assertEqual((view["status"], view["warning"]), (consent.OPTED_OUT, "red"))
		self.assertEqual(view["opted_out_source"], "Website")
		self.assertEqual(frappe.get_all("Consent Record", {"lead": self.lead}), [])
		row = next(r for r in caller_queue() if r["lead"] == self.lead)
		self.assertEqual((row["consent_status"], row["consent_warning"]), (consent.OPTED_OUT, "red"))

	def test_a_stop_from_an_unknown_number_is_recorded_on_a_new_lead(self):
		submit(self.form(stop="1"))
		client = frappe.db.get_value("Client", {"phone_key": FORM_PERSON}, "name")
		lead = frappe.db.get_value("Lead", {"client": client}, "name")
		self.assertEqual(consent.compute_status(lead), consent.OPTED_OUT)

	def test_it_does_not_block_a_later_call_sms_or_whatsapp_message(self):
		self.known_lead(FORM_PERSON)
		submit(self.form(stop="1"))
		for channel in consent.CHANNELS:
			check = consent.check_contact(self.lead, channel)
			self.assertFalse(check.refused, channel)
			self.assertEqual(check.warning_level, "red")

	def test_a_stop_by_message_uses_the_same_intake_function(self):
		result = intake.take(
			phone=STRANGER,
			source="Website",
			kind="message",
			reference="p208msg",
			evidence={"text": "STOP"},
			stop_source="WhatsApp",
		)
		self.assertTrue(result["stop"])
		self.assertEqual(consent.compute_status(result["lead"]), consent.OPTED_OUT)


class TestPublicIntakeChecks(EnquiryCase):
	"""SOS-P2-08: the shared checks of a public intake method."""

	def refused(self, body, **kw):
		before = counts()
		answer = submit(body, **kw)
		self.assertEqual(counts(), before, "a refused form writes nothing")
		return answer

	def test_a_bad_or_missing_key_and_an_invalid_field_get_the_same_short_answer(self):
		answers = {
			self.refused(self.form(key="wrong")),
			self.refused({k: v for k, v in self.form().items() if k != "key"}),
			self.refused(self.form(phone="not a number")),
			self.refused(self.form(name="")),
			self.refused(self.form(email="nope")),
			self.refused(self.form(name="x" * 101)),
			self.refused(self.form(unknown="field")),
			self.refused(self.form(message=["a list"])),
		}
		self.assertEqual(answers, {(public_intake.BAD_FORM_ANSWER, 400)})

	def test_a_filled_honeypot_gets_the_same_thank_you_and_writes_nothing(self):
		message, status = self.refused(self.form(website="http://spam.example"))
		self.assertIsNone(status)
		self.assertEqual(set(message), {"thank_you", "reference"})

	def test_a_body_over_the_cap_is_refused_before_it_is_read(self):
		message, status = self.refused(self.form(), extra_length=enquiry.MAX_BODY_BYTES + 1)
		self.assertEqual((message, status), ("too large", 413))

	def test_an_address_and_a_tenant_over_the_limit_are_refused(self):
		with patch("sellos.access.public_intake.over_address_limit", return_value=True):
			self.assertEqual(self.refused(self.form()), ("rate limited", 429))
		with patch("sellos.access.public_intake.over_rate_limit", return_value=True):
			self.assertEqual(self.refused(self.form()), ("rate limited", 429))

	def test_the_address_limit_counts_each_address_in_its_own_minute(self):
		address, other = "198.51.100.208", "198.51.100.209"
		now = 1_000_000.0
		path = "p208.test.path"
		self.assertFalse(public_intake.over_address_limit(path, address, 2, now))
		self.assertFalse(public_intake.over_address_limit(path, address, 2, now))
		self.assertTrue(public_intake.over_address_limit(path, address, 2, now))
		self.assertFalse(public_intake.over_address_limit(path, other, 2, now))
		self.assertFalse(public_intake.over_address_limit(path, address, 2, now + 120))

	def test_rotating_the_key_stops_the_old_link(self):
		frappe.set_user("Administrator")
		new_key = enquiry.rotate_enquiry_key.__wrapped__()["link"].split("?k=")[1]
		self.assertNotEqual(new_key, self.key)
		self.assertEqual(self.refused(self.form())[1], 400)
		message, status = submit(self.form(key=new_key))
		self.assertIsNone(status)
		self.assertIn("reference", message)

	def test_the_answer_sets_no_cookie_and_returns_no_record(self):
		# The test session may already hold a cookie from its own login: the answer adds none.
		manager = getattr(frappe.local, "cookie_manager", None)
		before = dict(manager.cookies) if manager else {}
		message, _ = submit(self.form())
		self.assertEqual(set(message), {"thank_you", "reference"})
		manager = getattr(frappe.local, "cookie_manager", None)
		after = dict(manager.cookies) if manager else {}
		self.assertEqual(after, before)

	def test_a_failure_inside_the_intake_is_refused_without_a_reason(self):
		with patch("sellos.crm.enquiry.intake.take", side_effect=RuntimeError("secret detail")):
			message, status = submit(self.form())
		self.assertEqual((message, status), (public_intake.BAD_FORM_ANSWER, 400))

	def test_a_method_without_its_checks_cannot_be_registered(self):
		with self.assertRaises(ValueError):
			public_intake.public_intake(
				fields={"a": public_intake.Field()},
				honeypot_field="",
				max_body_bytes=10,
				rate_limit_per_address=1,
				rate_limit_per_tenant=1,
				consent_evidence="x",
				calls_intake="sellos.crm.intake.take",
			)
		with self.assertRaises(ValueError):
			public_intake.public_intake(
				fields={"a": public_intake.Field()},
				honeypot_field="h",
				max_body_bytes=10,
				rate_limit_per_address=1,
				rate_limit_per_tenant=1,
				consent_evidence="x",
				calls_intake="sellos.crm.api.save_lead",
			)

	def test_the_request_guard_lets_the_registered_method_through_and_refuses_another(self):
		from sellos.access.registry import is_refused

		self.assertFalse(is_refused(SUBMIT))
		self.assertTrue(is_refused("sellos.crm.enquiry.not_registered"))

	def test_only_the_one_intake_function_makes_leads_for_both_routes(self):
		root = Path(enquiry.__file__).parent.parent
		for module in ("crm/enquiry.py", "telephony/inbound.py"):
			text = (root / module).read_text(encoding="utf-8")
			self.assertIn("intake.take(", text, module)
			self.assertNotIn('"doctype": "Lead"', text, module)


class TestRegressionSeed(InboundCase):
	"""SOS-P2-08: the regression data for the inbound opt in route, and the fixtures the spec uses."""

	def test_the_seed_makes_the_enquiry_and_missed_call_leads_and_is_safe_to_run_again(self):
		from sellos.tests import ui_fixtures

		ui_fixtures._seed_inbound_opt_in()
		first = counts()
		ui_fixtures._seed_inbound_opt_in()
		self.assertEqual(counts(), first)
		seeds = ui_fixtures.INBOUND_SEEDS
		state = {key: ui_fixtures.enquiry_outcome(phones.in_mobile(seeds[key])) for key in seeds}
		self.assertEqual(state["one"]["consent_status"], consent.CONSENTED)
		self.assertEqual(state["one"]["records"], ["Inquiry"])
		self.assertEqual(state["stop"]["consent_status"], consent.OPTED_OUT)
		self.assertEqual(state["stop"]["records"], [])
		self.assertEqual(state["missed"]["source"], "Missed call")
		self.assertEqual(state["missed"]["stage"], pipeline.first_stage())
		self.assertEqual(state["missed"]["consent_status"], consent.CONSENTED)

	def test_the_enquiry_fixture_gives_a_key_the_page_accepts_and_a_number_from_the_generator(self):
		from sellos.tests import ui_fixtures

		# The fixtures commit for the browser; here the test's own rollback must undo everything.
		patcher = patch.object(frappe.db, "commit")
		patcher.start()
		self.addCleanup(patcher.stop)
		made = ui_fixtures.seed_enquiry_page()
		self.assertTrue(public_intake.key_matches(made["key"]))
		self.assertEqual(made["phone"], phones.in_mobile(ui_fixtures.ENQUIRY_SEED))
		self.assertEqual(ui_fixtures.enquiry_outcome(), {"lead": None})
		submit(
			{
				"key": made["key"],
				"name": "Gate Enquiry Test",
				"phone": made["phone"],
				"website": "",
				"stop": "0",
			}
		)
		self.assertEqual(ui_fixtures.enquiry_outcome()["consent_status"], consent.CONSENTED)
		ui_fixtures.remove_enquiry_page()
		self.assertEqual(ui_fixtures.enquiry_outcome(), {"lead": None})
