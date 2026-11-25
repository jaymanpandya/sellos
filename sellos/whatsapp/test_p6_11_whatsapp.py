"""SOS-P6-11: the WhatsApp channel foundation, end to end through a fake provider behind the adapter.

A company connects its own number. A signed webhook body from the fake provider creates or updates a lead,
an opt in makes a Consent Record, a stop request is recorded as Opted out with a red warning and blocks
nothing, every send goes through the consent function and is linked to its Consent Check, and a
conversation can be handed to a human. The Meta adapter is tested against recorded answers, never the
real Meta. Tests use fake keys and numbers from sellos.tests.phones."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from sellos.access import webhooks
from sellos.crm import consent
from sellos.crm.test_crm import PHONE, CrmCase, as_user, email
from sellos.tests import phones
from sellos.whatsapp import conversations, settings, webhook
from sellos.whatsapp.base import InboundMessage, ProviderError, StatusEvent
from sellos.whatsapp.meta import MetaCloudProvider, TransportError, signature_header
from sellos.whatsapp.provider import FakeWhatsAppProvider, get_provider

SECRET = "p611-fake-signing-key-7a3e1c"
TOKEN = "FAKEOK-p611-token-42"
NUMBER_ID = "104829371650123"
STRANGER = phones.in_mobile(6101)
META_TO = phones.in_mobile(6151)
META_FROM = phones.in_mobile(6152)
PATH = "/api/method/sellos.whatsapp.webhook.whatsapp_event"
BASE = "https://tenant.example"
METHOD = "sellos.whatsapp.webhook.whatsapp_event"


def post(payload=None, body=None, secret=SECRET, signature=None, headers=None):
	"""Call the webhook as the provider does: a signed JSON post, as a guest."""
	body = body if body is not None else json.dumps(payload).encode()
	sent = {"Content-Type": "application/json", **(headers or {})}
	signature = signature if signature is not None else signature_header(body, secret)
	if signature:
		sent["X-Hub-Signature-256"] = signature
	environ = EnvironBuilder(method="POST", path=PATH, base_url=BASE, data=body, headers=sent)
	frappe.local.request = Request(environ.get_environ())
	frappe.local.response = frappe._dict()
	frappe.set_user("Guest")
	try:
		answer = webhook.whatsapp_event()
	finally:
		frappe.set_user("Administrator")
	return answer, frappe.local.response.get("http_status_code")


def inbound(text, sender=STRANGER, message_id=None, name="Meera Shah"):
	return {
		"messages": [
			{
				"id": message_id or f"wamid-{frappe.generate_hash(length=10)}",
				"from": sender,
				"text": text,
				"name": name,
			}
		]
	}


def status_of(message_id, status, error=""):
	return {"statuses": [{"id": message_id, "status": status, "error": error}]}


class WhatsAppCase(CrmCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.set_single_value("WhatsApp Settings", "provider", "fake")
		settings.save_whatsapp_settings(TOKEN, SECRET, NUMBER_ID, phones.in_mobile(6100))
		frappe.cache.delete_keys("sellos_webhook_rate")

	def writes(self):
		return {
			doctype: frappe.db.count(doctype)
			for doctype in (
				"Lead",
				"Client",
				"WhatsApp Message",
				"WhatsApp Conversation",
				"Consent Record",
				"Webhook Event",
				"Lead Activity",
			)
		}

	def receive(self, text, sender=STRANGER, **kw):
		answer = post(inbound(text, sender, **kw))
		self.assertEqual(answer, ("ok", None))
		return self.lead_of(sender)

	def lead_of(self, number):
		client = frappe.db.get_value("Client", {"phone": number})
		return frappe.db.get_value("Lead", {"client": client}) if client else None

	def thread(self, lead):
		return frappe.get_all(
			"WhatsApp Message",
			filters={"lead": lead},
			fields=["*"],
			order_by="creation asc, name asc",
		)

	def template(self, name="visit_reminder", status="Approved", body="Hello {{1}}, see you at {{2}}."):
		settings.save_whatsapp_template(name, body, status=status)
		return name


class TestRegistration(IntegrationTestCase):
	"""SOS-P6-11: the endpoint is a registered provider webhook that declares every check."""

	def test_it_is_registered_with_every_check_and_allows_guests(self):
		checks = webhooks.declared_webhooks()[METHOD]
		for name in ("signature", "replay", "max_body_bytes", "rate_limit_per_tenant", "secret_setting"):
			self.assertTrue(checks[name], name)
		self.assertEqual(checks["secret_setting"], "WhatsApp Settings.app_secret")
		self.assertIn(webhook.whatsapp_event, frappe.guest_methods)

	def test_the_request_guard_lets_it_through(self):
		from sellos.access.registry import is_refused, undeclared_whitelisted_methods

		self.assertFalse(is_refused(METHOD))
		self.assertNotIn(METHOD, undeclared_whitelisted_methods())

	def test_a_message_holds_no_consent_fields_of_its_own(self):
		fields = {f.fieldname for f in frappe.get_meta("WhatsApp Message").fields}
		self.assertIn("consent_check", fields)
		self.assertFalse(fields & {"consent_status", "warning", "warning_level", "refused", "enforcement"})
		for doctype in ("WhatsApp Message", "WhatsApp Conversation"):
			fieldnames = {f.fieldname for f in frappe.get_meta(doctype).fields}
			self.assertFalse(fieldnames & {"phone", "overseas_phone", "number", "wa_id"}, doctype)


class TestConnectingANumber(WhatsAppCase):
	"""SOS-P6-11: a company connects its own number through the provider adapter."""

	def test_the_settings_say_only_whether_each_key_is_set(self):
		state = settings.get_whatsapp_settings()
		self.assertEqual(
			(state["access_token_set"], state["app_secret_set"], state["configured"]), (True, True, True)
		)
		self.assertEqual(state["phone_number_id"], NUMBER_ID)
		self.assertNotIn(TOKEN, repr(state))
		self.assertNotIn(SECRET, repr(state))

	def test_a_blank_key_keeps_the_saved_one(self):
		settings.save_whatsapp_settings("", "", NUMBER_ID, None)
		self.assertEqual(settings._keys(), (TOKEN, SECRET))

	def test_the_connection_test_reports_success_and_the_provider_error_without_a_key(self):
		self.assertEqual(settings.check_whatsapp_connection()["ok"], True)
		settings.save_whatsapp_settings("WRONG-p611-token", None, None, None)
		answer = settings.check_whatsapp_connection()
		self.assertFalse(answer["ok"])
		self.assertNotIn("WRONG-p611-token", answer["message"])
		settings.save_whatsapp_settings("FAKEDOWN-p611-token", None, None, None)
		self.assertIn("could not be reached", settings.check_whatsapp_connection()["message"])

	def test_a_company_with_no_number_gets_a_clear_message(self):
		frappe.db.set_single_value("WhatsApp Settings", "phone_number_id", "")
		self.assertIn("not connected", settings.check_whatsapp_connection()["message"])

	def test_a_number_id_is_digits_only(self):
		with self.assertRaises(frappe.ValidationError):
			settings.save_whatsapp_settings(None, None, "12 ab", None)

	def test_the_live_meta_adapter_never_runs_on_a_test_site(self):
		frappe.db.set_single_value("WhatsApp Settings", "provider", "")
		with self.assertRaises(ProviderError):
			get_provider(TOKEN, NUMBER_ID)
		frappe.db.set_single_value("WhatsApp Settings", "provider", "nonesuch")
		with self.assertRaises(ProviderError):
			get_provider(TOKEN, NUMBER_ID)

	def test_only_a_company_admin_may_change_the_settings(self):
		for key in ("agent", "sales_manager", "channel_partner", "client"):
			as_user(key)
			with self.assertRaises(frappe.PermissionError, msg=key):
				settings.save_whatsapp_settings(TOKEN, None, None, None)
		frappe.set_user("Administrator")

	def test_templates_are_validated_and_never_deleted(self):
		with self.assertRaises(frappe.ValidationError):
			settings.save_whatsapp_template("Bad Name!", "x")
		self.template("hello_there")
		row = settings.save_whatsapp_template("hello_there", "Changed", enabled=0)
		self.assertEqual((row["body"], row["enabled"]), ("Changed", 0))
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("WhatsApp Template", "hello_there")
		as_user("agent")
		self.assertEqual(settings.list_whatsapp_templates(), [])  # off, so a sender is not offered it
		frappe.set_user("Administrator")
		self.assertEqual(len(settings.list_whatsapp_templates(include_disabled=1)), 1)


class TestMetaAdapter(IntegrationTestCase):
	"""SOS-P6-11: the Meta Cloud API adapter, against recorded answers. The real Meta is never called."""

	def provider(self, status=200, answer=None):
		self.calls = []

		def transport(method, url, token, body=None):
			self.calls.append((method, url, token, body))
			if isinstance(answer, Exception):
				raise answer
			return status, json.dumps(answer or {}).encode()

		return MetaCloudProvider("meta-token-p611", NUMBER_ID, transport=transport)

	def test_a_text_and_a_template_are_sent_in_metas_shape(self):
		provider = self.provider(answer={"messages": [{"id": "wamid.ABC"}]})
		self.assertEqual(provider.send_text(META_TO, "Hi").message_id, "wamid.ABC")
		method, url, token, body = self.calls[-1]
		self.assertEqual((method, token), ("POST", "meta-token-p611"))
		self.assertTrue(
			url.endswith(f"/{NUMBER_ID}/messages") and url.startswith("https://graph.facebook.com/")
		)
		self.assertEqual(
			body,
			{"messaging_product": "whatsapp", "to": META_TO[1:], "type": "text", "text": {"body": "Hi"}},
		)
		provider.send_template(META_TO, "visit_reminder", "en", ["Asha", "10 am"])
		template = self.calls[-1][3]["template"]
		self.assertEqual(template["name"], "visit_reminder")
		self.assertEqual([p["text"] for p in template["components"][0]["parameters"]], ["Asha", "10 am"])

	def test_failures_become_clear_messages_with_no_key(self):
		cases = (
			(401, {}, "refused this access token"),
			(400, {"error": {"code": 131047}}, "24 hour window"),
			(400, {"error": {"code": 131026}}, "could not deliver"),
			(429, {}, "limiting"),
			(503, {}, "having a problem"),
			(400, {"error": {"message": "bad meta-token-p611 thing"}}, "rejected the message: bad ***"),
		)
		for status, answer, text in cases:
			with self.assertRaises(ProviderError) as caught:
				self.provider(status, answer).send_text(META_TO, "Hi")
			self.assertIn(text, str(caught.exception))
			self.assertNotIn("meta-token-p611", str(caught.exception))
		with self.assertRaises(ProviderError) as caught:
			self.provider(answer=TransportError()).test_connection()
		self.assertIn("could not be reached", str(caught.exception))
		with self.assertRaises(ProviderError):
			self.provider(answer={}).send_text(META_TO, "Hi")  # no message id came back

	def test_a_meta_webhook_body_becomes_messages_and_statuses(self):
		value = {
			"metadata": {"phone_number_id": NUMBER_ID},
			"contacts": [{"wa_id": META_FROM[1:], "profile": {"name": "Ravi"}}],
			"messages": [
				{"id": "wamid.IN1", "from": META_FROM[1:], "type": "text", "text": {"body": "STOP"}},
				{"id": "wamid.IN2", "from": META_FROM[1:], "type": "image"},
			],
			"statuses": [{"id": "wamid.OUT1", "status": "delivered"}, {"id": "x", "status": "odd"}],
		}
		other = {
			"metadata": {"phone_number_id": "999"},
			"messages": [{"id": "z", "from": "9", "type": "text"}],
		}
		body = json.dumps(
			{
				"object": "whatsapp_business_account",
				"entry": [{"changes": [{"value": value}, {"value": other}]}],
			}
		).encode()
		events = self.provider().read_webhook(body)
		self.assertEqual(
			[(type(e).__name__, e.message_id) for e in events],
			[("InboundMessage", "wamid.IN1"), ("InboundMessage", "wamid.IN2"), ("StatusEvent", "wamid.OUT1")],
		)
		self.assertEqual((events[0].from_number, events[0].text, events[0].name), (META_FROM, "STOP", "Ravi"))
		self.assertEqual(events[1].text, "")
		with self.assertRaises(ProviderError):
			self.provider().read_webhook(b"not json")

	def test_the_signature_is_metas_sha256_header(self):
		self.assertTrue(signature_header(b"{}", "k").startswith("sha256="))
		self.assertEqual(signature_header(b"{}", "k"), signature_header(b"{}", "k"))
		self.assertNotEqual(signature_header(b"{}", "k"), signature_header(b"{}", "j"))


class TestClassify(IntegrationTestCase):
	def test_only_a_whole_message_is_a_stop_or_an_opt_in(self):
		for text in ("STOP", " stop. ", "Unsubscribe", "opt-out", "Please stop"):
			self.assertEqual(conversations.classify(text), "Stop", text)
		for text in ("START", "Opt in!", "I agree"):
			self.assertEqual(conversations.classify(text), "Opt in", text)
		for text in ("do not stop the visit", "start at 5", "stopping by", "", "2 BHK please"):
			self.assertEqual(conversations.classify(text), "", text)


class TestInboundMessages(WhatsAppCase):
	"""SOS-P6-11: messages create or update leads."""

	def test_a_message_from_a_stranger_makes_a_client_a_lead_and_a_conversation(self):
		lead = self.receive("Hi, I want a 2 BHK in Powai")
		row = frappe.db.get_value("Lead", lead, ["source", "consent_status", "client"], as_dict=True)
		self.assertEqual((row.source, row.consent_status), ("WhatsApp", "Unknown"))
		self.assertEqual(frappe.db.get_value("Client", row.client, "client_name"), "Meera Shah")
		message = self.thread(lead)[0]
		self.assertEqual(
			(message.direction, message.status, message.body, message.intent),
			("Inbound", "received", "Hi, I want a 2 BHK in Powai", ""),
		)
		conversation = frappe.get_doc("WhatsApp Conversation", message.conversation)
		self.assertEqual((conversation.lead, conversation.state), (lead, "Open"))
		self.assertTrue(conversation.last_inbound_on)
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": lead, "activity_type": "WhatsApp"}), 1)
		self.assertEqual(
			frappe.db.count("Consent Record", {"lead": lead}), 0
		)  # a plain message is not an opt in

	def test_a_second_message_updates_the_same_lead(self):
		lead = self.receive("Hello")
		before = self.writes()
		self.assertEqual(self.receive("Is parking included?"), lead)
		after = self.writes()
		self.assertEqual(
			(after["Lead"], after["Client"], after["WhatsApp Conversation"]),
			(before["Lead"], before["Client"], before["WhatsApp Conversation"]),
		)
		self.assertEqual(after["WhatsApp Message"], before["WhatsApp Message"] + 1)
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": lead, "activity_type": "WhatsApp"}), 2)

	def test_a_message_from_a_known_number_updates_that_lead_and_keeps_its_stage(self):
		_client, lead = self.make_lead()
		frappe.set_user("Administrator")
		stage = frappe.db.get_value("Lead", lead, "stage")
		before = frappe.db.count("Lead")
		self.assertEqual(self.receive("Hi again", sender=PHONE), lead)
		self.assertEqual(frappe.db.count("Lead"), before)
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), stage)
		self.assertEqual(frappe.db.get_value("Lead", lead, "source"), "Website")

	def test_a_message_id_is_taken_once(self):
		self.receive("Hello", message_id="wamid-once")
		before = self.writes()
		self.assertIsNone(conversations.receive(InboundMessage("wamid-once", STRANGER, "Hello again")))
		self.assertEqual(self.writes(), before)

	def test_a_closed_conversation_reopens_when_the_customer_writes(self):
		lead = self.receive("Hello")
		name = self.thread(lead)[0].conversation
		frappe.db.set_value("WhatsApp Conversation", name, "state", "Closed")
		self.receive("Anyone there?")
		self.assertEqual(frappe.db.get_value("WhatsApp Conversation", name, "state"), "Open")

	def test_a_company_that_switched_the_whatsapp_source_off_still_gets_the_lead(self):
		self.receive("Hello")
		frappe.db.set_value("Lead Source", "WhatsApp", "enabled", 0)
		lead = self.receive("Hello", sender=phones.in_mobile(6102))
		self.assertEqual(frappe.db.get_value("Lead", lead, "source"), "Website")


class TestOptInAndStop(WhatsAppCase):
	"""SOS-P6-11: an opt in makes a Consent Record, a stop request is Opted out with a red warning."""

	def test_an_opt_in_makes_a_consent_record_with_the_message_as_private_evidence(self):
		lead = self.receive("START")
		records = frappe.get_all(
			"Consent Record", filters={"lead": lead}, fields=["name", "basis", "evidence_link", "expires_on"]
		)
		self.assertEqual(len(records), 1)
		record = records[0]
		self.assertEqual((record.basis, record.expires_on), ("Consent", None))
		self.assertTrue(record.evidence_link.startswith("/private/files/"))
		file = frappe.get_doc("File", {"file_url": record.evidence_link})
		self.assertEqual(
			(file.is_private, file.attached_to_doctype, file.attached_to_name), (1, "Lead", lead)
		)
		saved = json.loads(file.get_content())
		self.assertEqual((saved["text"], saved["intent"], saved["channel"]), ("START", "Opt in", "WhatsApp"))
		message = self.thread(lead)[0]
		self.assertEqual(
			(message.intent, message.consent_record, message.evidence_link),
			("Opt in", record.name, record.evidence_link),
		)
		self.assertEqual(frappe.db.get_value("Lead", lead, "consent_status"), "Consented")

	def test_a_stop_request_is_recorded_as_opted_out_with_a_red_warning(self):
		lead = self.receive("Hello")
		self.receive("STOP")
		self.assertEqual(consent.compute_status(lead), "Opted out")
		view = consent.consent_view(lead)
		self.assertEqual(view["warning"], "red")
		self.assertEqual(view["opted_out_source"], "WhatsApp")
		message = self.thread(lead)[-1]
		self.assertEqual(message.intent, "Stop")
		self.assertTrue(message.evidence_link.startswith("/private/files/"))
		self.assertEqual(frappe.db.count("Consent Record", {"lead": lead}), 0)  # a stop makes no inquiry
		self.assertEqual(frappe.db.get_value("Lead", lead, "consent_status"), "Opted out")

	def test_a_stop_from_a_consented_lead_wins_and_a_later_opt_in_does_not_clear_it(self):
		lead = self.receive("START")
		self.receive("stop")
		self.assertEqual(consent.compute_status(lead), "Opted out")
		self.receive("START")
		self.assertEqual(consent.compute_status(lead), "Opted out")
		self.assertEqual(frappe.db.count("Consent Record", {"lead": lead}), 2)

	def test_later_messages_from_an_opted_out_lead_are_still_taken_and_not_blocked(self):
		lead = self.receive("STOP")
		self.assertEqual(self.receive("Actually, what is the price?"), lead)
		self.assertEqual(len(self.thread(lead)), 2)
		as_user("company_admin")
		result = conversations.send(lead, template=self.template())
		self.assertTrue(result["sent"])
		self.assertFalse(result["refused"])


class TestOutboundMessages(WhatsAppCase):
	"""SOS-P6-11: every send goes through the consent function and is linked to its Consent Check."""

	def lead_with_window(self, text="Hello"):
		lead = self.receive(text)
		as_user("company_admin")
		return lead

	def test_a_send_records_the_consent_status_and_warning_on_its_check(self):
		lead = self.lead_with_window()
		result = conversations.send(lead, text="Thanks for writing")
		self.assertTrue(result["sent"])
		self.assertEqual((result["consent_status"], result["consent_warning"]), ("Unknown", "amber"))
		message = frappe.get_doc("WhatsApp Message", result["message"])
		self.assertEqual(
			(message.direction, message.status, message.sent_by), ("Outbound", "sent", email("company_admin"))
		)
		self.assertTrue(message.provider_message_id.startswith("fakewa-"))
		check = frappe.get_doc("Consent Check", message.consent_check)
		self.assertEqual(
			(
				check.channel,
				check.lead,
				check.consent_status,
				check.warning_level,
				check.enforcement,
				check.refused,
			),
			("WhatsApp", lead, "Unknown", "amber", "Off", 0),
		)
		self.assertTrue(check.warning)
		self.assertEqual((check.reference_doctype, check.reference_name), ("WhatsApp Message", message.name))

	def test_every_consent_status_is_sent_while_enforcement_is_off(self):
		lead = self.lead_with_window()
		for status, setup in (
			("Unknown", lambda: None),
			("Registered DND", lambda: consent.record_dnd_result(lead, True)),
			("Opted out", lambda: consent.record_opt_out(lead, "WhatsApp")),
		):
			setup()
			result = conversations.send(lead, text=f"Update for {status}")
			self.assertTrue(result["sent"], status)
			self.assertFalse(result["refused"], status)
			check = frappe.get_doc(
				"Consent Check", frappe.db.get_value("WhatsApp Message", result["message"], "consent_check")
			)
			self.assertEqual((check.consent_status, check.refused, check.enforcement), (status, 0, "Off"))
		self.assertEqual(result["consent_warning"], "red")

	def test_enforcement_on_is_the_only_thing_that_refuses_and_the_check_is_kept(self):
		lead = self.lead_with_window()
		consent.set_enforcement(True)
		before = frappe.db.count("WhatsApp Message")
		result = conversations.send(lead, text="Hello?")
		self.assertTrue(result["refused"] and not result["sent"])
		self.assertIn("Consent enforcement is On", result["reason"])
		self.assertEqual(frappe.db.count("WhatsApp Message"), before)
		check = frappe.get_all(
			"Consent Check", filters={"lead": lead, "channel": "WhatsApp"}, fields=["refused", "enforcement"]
		)[-1]
		self.assertEqual((check.refused, check.enforcement), (1, "On"))
		self.receive("START")
		as_user("company_admin")
		self.assertTrue(conversations.send(lead, text="Welcome")["sent"])

	def test_free_text_needs_the_24_hour_window_and_a_template_does_not(self):
		_client, lead = self.make_lead()
		as_user("company_admin")
		with self.assertRaises(frappe.ValidationError) as caught:
			conversations.send(lead, text="Hello")
		self.assertIn("24 hour window", str(caught.exception))
		self.assertEqual(frappe.db.count("Consent Check", {"lead": lead}), 0)
		self.assertTrue(
			conversations.send(lead, template=self.template(), parameters=["Asha", "10 am"])["sent"]
		)
		message = self.thread(lead)[-1]
		self.assertEqual((message.kind, message.body), ("Template", "Hello Asha, see you at 10 am."))
		conversation = message.conversation
		old = frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-25)
		frappe.db.set_value("WhatsApp Conversation", conversation, "last_inbound_on", old)
		self.assertFalse(conversations.window_open(conversation))
		frappe.db.set_value(
			"WhatsApp Conversation", conversation, "last_inbound_on", frappe.utils.add_to_date(old, hours=2)
		)
		self.assertTrue(conversations.window_open(conversation))

	def test_a_template_must_be_enabled_and_approved(self):
		lead = self.lead_with_window()
		for name in ("pending_one", "missing_one"):
			if name == "pending_one":
				frappe.set_user("Administrator")
				self.template(name, status="Pending")
				as_user("company_admin")
			with self.assertRaises(frappe.ValidationError):
				conversations.send(lead, template=name)
		with self.assertRaises(frappe.ValidationError):
			conversations.send(lead)
		with self.assertRaises(frappe.ValidationError):
			conversations.send(lead, text="x", template="y")

	def test_a_provider_failure_is_kept_on_the_thread_with_no_key_in_it(self):
		lead = self.lead_with_window()
		frappe.set_user("Administrator")
		settings.save_whatsapp_settings("FAKEDOWN-p611-token", None, None, None)
		as_user("company_admin")
		result = conversations.send(lead, text="Hello")
		self.assertFalse(result["sent"] or result["refused"])
		self.assertIn("could not be reached", result["error"])
		message = frappe.get_doc("WhatsApp Message", result["message"])
		self.assertEqual(message.status, "failed")
		self.assertNotIn("FAKEDOWN-p611-token", message.error)
		self.assertTrue(frappe.db.get_value("Consent Check", message.consent_check, "name"))

	def test_a_company_with_no_number_cannot_send(self):
		lead = self.lead_with_window()
		frappe.db.set_single_value("WhatsApp Settings", "phone_number_id", "")
		with self.assertRaises(frappe.ValidationError) as caught:
			conversations.send(lead, text="Hello")
		self.assertIn("not connected", str(caught.exception))

	def test_an_agent_sends_only_on_their_own_leads(self):
		_client, lead = self.make_lead()  # the agent's lead
		frappe.set_user("Administrator")
		self.receive("Hello", sender=PHONE)
		as_user("agent")
		self.assertTrue(conversations.send(lead, text="Hi Asha")["sent"])
		as_user("sales_manager")
		with self.assertRaises(frappe.PermissionError):
			conversations.send(lead, text="Not my team")
		as_user("channel_partner")
		with self.assertRaises(frappe.PermissionError):
			conversations.send_whatsapp_message(lead, text="Not mine")

	def test_the_screen_never_returns_a_phone_number(self):
		lead = self.lead_with_window()
		conversations.send(lead, text="Hello")
		rows = conversations.list_for_screen()
		thread = conversations.thread_for_screen(rows[0].name)
		for value in (rows, thread):
			self.assertNotIn(STRANGER[-10:], repr(value))
			self.assertNotIn(STRANGER, repr(value))
		self.assertEqual(thread["messages"][-1]["consent_status"], "Unknown")
		self.assertEqual(thread["consent_warning"], "amber")

	def test_the_list_row_has_a_masked_phone_and_the_last_message_for_every_role(self):
		# SOS-LOOP: the conversation list shows the lead name, the phone below it (masked, last three digits),
		# the last message and its time. The full number is never in the list, even for a Company Admin.
		lead = self.lead_with_window()
		conversations.send(lead, text="First hello")
		conversations.send(lead, text="Second hello, with   odd\n spacing")
		for role in ("administrator", "company_admin"):
			if role == "company_admin":
				as_user(role)
			row = conversations.list_for_screen()[0]
			self.assertTrue(row["phone"].endswith(STRANGER[-3:]))
			self.assertEqual(set(row["phone"]) - {"*"}, set(STRANGER[-3:]))
			self.assertNotIn(STRANGER[-10:], repr(row))
			self.assertEqual(row["last_message"], "Second hello, with odd spacing")
			self.assertTrue(row["last_message_on"])


class TestStatuses(WhatsAppCase):
	"""SOS-P6-11: delivery statuses arrive through the webhook and are applied in order."""

	def sent_message(self):
		lead = self.receive("Hello")
		as_user("company_admin")
		result = conversations.send(lead, text="Hi")
		frappe.set_user("Administrator")
		return frappe.db.get_value("WhatsApp Message", result["message"], "provider_message_id"), result[
			"message"
		]

	def status(self, name):
		return frappe.db.get_value("WhatsApp Message", name, "status")

	def test_delivered_and_read_move_the_message_along_and_a_late_one_is_ignored(self):
		wa_id, name = self.sent_message()
		self.assertEqual(post(status_of(wa_id, "delivered")), ("ok", None))
		self.assertEqual(self.status(name), "delivered")
		post(status_of(wa_id, "read"))
		self.assertEqual(self.status(name), "read")
		post(status_of(wa_id, "sent"))
		post(status_of(wa_id, "delivered"))
		post(status_of(wa_id, "failed", "late"))
		self.assertEqual(self.status(name), "read")

	def test_a_failure_keeps_its_reason_and_an_unknown_message_is_ignored(self):
		wa_id, name = self.sent_message()
		post(status_of(wa_id, "failed", "Not on WhatsApp"))
		self.assertEqual(
			(self.status(name), frappe.db.get_value("WhatsApp Message", name, "error")),
			("failed", "Not on WhatsApp"),
		)
		before = self.writes()
		self.assertEqual(post(status_of("wamid-unknown", "read")), ("ok", None))
		self.assertEqual(self.writes()["WhatsApp Message"], before["WhatsApp Message"])
		self.assertIsNone(conversations.apply_status(StatusEvent("wamid-unknown", "odd")))


class TestSignedWebhook(WhatsAppCase):
	"""SOS-P6-11: signature first, replay, size and rate, the secret never logged."""

	def test_an_invalid_or_missing_signature_writes_nothing_and_reveals_nothing(self):
		body = json.dumps(inbound("Hello")).encode()
		before = self.writes()
		answers = [
			post(body=body, signature=""),
			post(body=body, signature="sha256=" + "0" * 64),
			post(body=body, secret="another-key"),
			post(body=body, signature=signature_header(body, SECRET).replace("sha256=", "")),
			post(body=body, signature=" "),
			post(body=body + b" ", signature=signature_header(body, SECRET)),  # tampered after signing
		]
		self.assertEqual(set(answers), {("refused", 403)})
		self.assertEqual(self.writes(), before)

	def test_with_no_secret_saved_every_request_is_refused(self):
		frappe.db.delete("__Auth", {"doctype": "WhatsApp Settings", "fieldname": "app_secret"})
		before = self.writes()
		self.assertEqual(post(inbound("Hello")), ("refused", 403))
		self.assertEqual(self.writes(), before)

	def test_the_tenant_is_the_site_and_not_a_header(self):
		answer = post(inbound("Hello"), headers={"X-Tenant": "other", "Host": "other.example"})
		self.assertEqual(answer, ("ok", None))
		self.assertIsNotNone(self.lead_of(STRANGER))  # it landed in this site's database

	def test_a_replayed_body_changes_nothing(self):
		body = json.dumps(inbound("Hello", message_id="wamid-replay")).encode()
		self.assertEqual(post(body=body), ("ok", None))
		first = self.writes()
		self.assertEqual(post(body=body), ("ignored", None))
		self.assertEqual(self.writes(), first)

	def test_a_message_id_sent_again_in_another_body_is_not_taken_twice(self):
		self.assertEqual(post(inbound("Hello", message_id="wamid-twice")), ("ok", None))
		first = self.writes()
		post(inbound("Hello", message_id="wamid-twice", name="Other Name"))
		self.assertEqual(self.writes()["WhatsApp Message"], first["WhatsApp Message"])

	def test_an_unreadable_but_signed_body_is_ignored(self):
		self.assertEqual(post(body=b"not json at all"), ("ignored", None))
		self.assertEqual(post(payload=[1, 2]), ("ignored", None))

	def test_an_oversized_body_is_refused_before_anything_is_written(self):
		before = self.writes()
		big = inbound("x" * webhook.MAX_BODY_BYTES)
		self.assertEqual(post(big), ("too large", 413))
		self.assertEqual(self.writes(), before)

	def test_the_cap_is_checked_from_the_declared_length_before_the_body_is_read(self):
		with patch.object(Request, "get_data", side_effect=AssertionError("body was read")):
			environ = EnvironBuilder(method="POST", path=PATH, base_url=BASE, data=b"{}").get_environ()
			environ["CONTENT_LENGTH"] = str(webhook.MAX_BODY_BYTES + 1)
			frappe.local.request = Request(environ)
			frappe.local.response = frappe._dict()
			self.assertEqual(webhook.whatsapp_event(), "too large")

	def test_requests_over_the_limit_are_refused_and_write_nothing(self):
		with patch("sellos.access.webhooks.time.time", return_value=1_700_000_000):
			for _count in range(webhook.REQUESTS_PER_MINUTE):
				self.assertFalse(webhooks.over_rate_limit(METHOD, webhook.REQUESTS_PER_MINUTE, 1_700_000_000))
			before = self.writes()
			self.assertEqual(post(inbound("Hello")), ("rate limited", 429))
			self.assertEqual(self.writes(), before)

	def test_the_signing_secret_and_token_appear_nowhere(self):
		answers = [post(inbound("Hello")), post(inbound("Hi"), secret="wrong-key")]
		with patch("frappe.logger") as logger:
			post(inbound("STOP"))
		self.assertFalse(logger.called)
		self.assertNotIn(SECRET, repr(answers))
		self.assertFalse([e for e in frappe.get_all("Error Log", pluck="error") if SECRET in e or TOKEN in e])
		for doctype in (
			"Webhook Event",
			"WhatsApp Message",
			"WhatsApp Conversation",
			"Version",
			"Activity Log",
		):
			rows = repr(frappe.get_all(doctype, fields=["*"]))
			self.assertNotIn(SECRET, rows, doctype)
			self.assertNotIn(TOKEN, rows, doctype)


class TestHandoff(WhatsAppCase):
	"""SOS-P6-11: a conversation can be handed to a human."""

	def conversation(self):
		_client, lead = self.make_lead()
		frappe.set_user("Administrator")
		self.receive("Hello, a human please", sender=PHONE)
		return lead, frappe.db.get_value("WhatsApp Conversation", {"lead": lead})

	def test_the_lead_agent_takes_the_conversation_and_it_is_logged(self):
		lead, name = self.conversation()
		as_user("agent")
		answer = conversations.hand_off(name, note="Wants a call tonight")
		self.assertEqual((answer["state"], answer["handed_to"]), ("With a human", email("agent")))
		row = frappe.db.get_value(
			"WhatsApp Conversation", name, ["state", "handed_to", "handoff_note", "handed_on"], as_dict=True
		)
		self.assertEqual(
			(row.state, row.handed_to, row.handoff_note),
			("With a human", email("agent"), "Wants a call tonight"),
		)
		self.assertTrue(row.handed_on)
		notes = frappe.get_all(
			"Lead Activity", filters={"lead": lead, "activity_type": "WhatsApp"}, pluck="notes"
		)
		self.assertTrue(any("handed to" in n and "Wants a call tonight" in n for n in notes))
		self.assertEqual(conversations.thread_for_screen(name)["state"], "With a human")

	def test_a_company_admin_hands_it_to_a_named_person_who_is_told(self):
		_lead, name = self.conversation()
		as_user("company_admin")
		conversations.hand_off(name, to_user=email("agent"))
		self.assertEqual(frappe.db.get_value("WhatsApp Conversation", name, "handed_to"), email("agent"))
		told = frappe.get_all(
			"App Notification", filters={"recipient": email("agent"), "event": "WhatsApp handoff"}
		)
		self.assertEqual(len(told), 1)

	def test_it_can_only_go_to_a_person_who_works_leads(self):
		_lead, name = self.conversation()
		as_user("company_admin")
		for key in ("client", "channel_partner", "basic"):
			with self.assertRaises(frappe.ValidationError, msg=key):
				conversations.hand_off(name, to_user=email(key))
		with self.assertRaises(frappe.ValidationError):
			conversations.hand_off(name, to_user="nobody@example.com")

	def test_only_someone_who_may_see_the_lead_may_hand_it_off(self):
		_lead, name = self.conversation()
		for key in ("channel_partner", "client"):
			as_user(key)
			with self.assertRaises(frappe.PermissionError, msg=key):
				conversations.hand_off_whatsapp_conversation(name)

	def test_a_customer_message_leaves_a_handed_over_conversation_with_the_human_and_it_can_be_closed(self):
		_lead, name = self.conversation()
		as_user("agent")
		conversations.hand_off(name)
		frappe.set_user("Administrator")
		self.receive("Still there?", sender=PHONE)
		self.assertEqual(frappe.db.get_value("WhatsApp Conversation", name, "state"), "With a human")
		as_user("agent")
		self.assertEqual(conversations.close(name)["state"], "Closed")


class TestVisibility(WhatsAppCase):
	"""SOS-P6-11: a conversation is as visible as its lead."""

	def test_an_agent_sees_only_the_conversations_of_their_own_leads(self):
		_client, own = self.make_lead()
		frappe.set_user("Administrator")
		self.receive("Hello", sender=PHONE)
		self.receive("Hello", sender=STRANGER)  # unassigned: only the Company Admin sees it
		as_user("agent")
		self.assertEqual([row.lead for row in conversations.list_for_screen()], [own])
		as_user("company_admin")
		self.assertEqual(len(conversations.list_for_screen()), 2)
		as_user("channel_partner")
		with self.assertRaises(frappe.PermissionError):
			conversations.list_whatsapp_conversations()
		as_user("agent")
		other = frappe.db.get_value("WhatsApp Conversation", {"lead": self.lead_of(STRANGER)})
		with self.assertRaises(frappe.PermissionError):
			conversations.get_whatsapp_conversation(other)

	def test_nothing_is_deleted(self):
		lead = self.receive("Hello")
		for doctype, name in (
			("WhatsApp Message", self.thread(lead)[0].name),
			("WhatsApp Conversation", self.thread(lead)[0].conversation),
		):
			with self.assertRaises(frappe.PermissionError, msg=doctype):
				frappe.delete_doc(doctype, name, force=True)


class TestEndToEnd(WhatsAppCase):
	"""SOS-P6-11: the whole path through the fake provider with signed bodies."""

	def test_inbound_outbound_opt_in_stop_and_handoff(self):
		# 1. a stranger writes: a client, a lead and a conversation appear
		lead = self.receive("Hi, do you have a 2 BHK in Andheri?")
		self.assertEqual(consent.compute_status(lead), "Unknown")
		# 2. the Company Admin answers inside the 24 hour window; the check says Unknown with an amber warning
		as_user("company_admin")
		reply = conversations.send_whatsapp_message(lead, text="Yes, we do. Shall I send the brochure?")
		self.assertTrue(reply["sent"])
		self.assertEqual((reply["consent_status"], reply["consent_warning"]), ("Unknown", "amber"))
		provider_id = frappe.db.get_value("WhatsApp Message", reply["message"], "provider_message_id")
		frappe.set_user("Administrator")
		post(status_of(provider_id, "delivered"))
		post(status_of(provider_id, "read"))
		self.assertEqual(frappe.db.get_value("WhatsApp Message", reply["message"], "status"), "read")
		# 3. the customer opts in: a Consent Record with private evidence
		self.receive("START")
		self.assertEqual(consent.compute_status(lead), "Consented")
		record = frappe.get_all(
			"Consent Record", filters={"lead": lead, "basis": "Consent"}, pluck="evidence_link"
		)
		self.assertTrue(record[0].startswith("/private/files/"))
		as_user("company_admin")
		self.assertEqual(
			conversations.send(lead, template=self.template(), parameters=["Meera", "4 pm"])[
				"consent_warning"
			],
			"none",
		)
		# 4. the customer asks to stop: Opted out with a red warning, and the next message still goes
		frappe.set_user("Administrator")
		self.receive("STOP")
		view = consent.consent_view(lead)
		self.assertEqual((view["status"], view["warning"]), ("Opted out", "red"))
		as_user("company_admin")
		after_stop = conversations.send(lead, text="We have stopped. One last note: your visit is booked.")
		self.assertTrue(after_stop["sent"] and not after_stop["refused"])
		self.assertEqual(after_stop["consent_warning"], "red")
		# 5. it is handed to a human
		name = frappe.db.get_value("WhatsApp Conversation", {"lead": lead})
		conversations.hand_off_whatsapp_conversation(name, to_user=email("agent"), note="Call after 6")
		thread = conversations.get_whatsapp_conversation(name)
		self.assertEqual((thread["state"], thread["handed_to"]), ("With a human", email("agent")))
		self.assertEqual(
			[(m["direction"], m["intent"]) for m in thread["messages"]],
			[
				("Inbound", ""),
				("Outbound", ""),
				("Inbound", "Opt in"),
				("Outbound", ""),
				("Inbound", "Stop"),
				("Outbound", ""),
			],
		)
		self.assertEqual(thread["messages"][-1]["consent_warning"], "red")


class TestFakeProvider(IntegrationTestCase):
	def test_the_fake_provider_reads_its_own_bodies(self):
		provider = FakeWhatsAppProvider(TOKEN, NUMBER_ID)
		events = provider.read_webhook(
			json.dumps({**inbound("hi", META_TO), **status_of("w1", "read")}).encode()
		)
		self.assertEqual([type(e).__name__ for e in events], ["InboundMessage", "StatusEvent"])
		with self.assertRaises(ProviderError):
			provider.read_webhook(b"[")


class TestRegressionSeed(WhatsAppCase):
	"""SOS-P6-11: the regression data for the WhatsApp flows, and the fixtures the spec uses."""

	def setUp(self):
		super().setUp()
		# The fixtures commit for the browser; here the test's own rollback must undo everything.
		patcher = patch.object(frappe.db, "commit")
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_the_regression_seed_makes_three_conversations_and_is_safe_to_run_again(self):
		from sellos.tests import ui_fixtures as fx

		admin, agent = email("company_admin"), email("agent")
		fx._seed_whatsapp(admin, agent)
		first = self.writes()
		fx._seed_whatsapp(admin, agent)
		self.assertEqual(self.writes(), first)
		leads = {
			key: frappe.db.get_value(
				"Lead",
				{
					"client": frappe.db.get_value(
						"Client", {"client_name": f"{fx.REGRESSION_PREFIX}WhatsApp {key.title()}"}
					)
				},
			)
			for key in fx.WHATSAPP_REGRESSION_SEEDS
		}
		self.assertTrue(all(leads.values()))
		nine = [(m.direction, m.status) for m in self.thread(leads["nine"])]
		self.assertEqual(nine, [("Inbound", "received"), ("Outbound", "delivered")])
		self.assertEqual(consent.compute_status(leads["nine"]), "Unknown")
		self.assertEqual(consent.compute_status(leads["ten"]), "Consented")
		ten = frappe.db.get_value("WhatsApp Conversation", {"lead": leads["ten"]}, ["state", "handed_to"])
		self.assertEqual(tuple(ten), ("With a human", agent))
		self.assertEqual(consent.compute_status(leads["eleven"]), "Opted out")
		eleven = [(m.direction, m.intent) for m in self.thread(leads["eleven"])]
		self.assertEqual(eleven, [("Inbound", "Stop"), ("Outbound", "")])
		self.assertEqual(settings.get_whatsapp_settings()["configured"], True)
		self.assertEqual(frappe.db.get_value("WhatsApp Template", fx.WHATSAPP_TEMPLATE, "status"), "Approved")

	def test_the_spec_fixtures_make_a_signed_body_the_webhook_accepts_and_clean_up(self):
		from sellos.tests import ui_fixtures as fx

		made = fx.seed_whatsapp()
		self.assertEqual(consent.compute_status(made["lead"]), "Unknown")
		signed = fx.whatsapp_signed_body("START", "wamid-fixture-optin")
		self.assertEqual(
			post(body=signed["body"].encode(), signature=signed["signature"], secret=fx.WHATSAPP_SECRET),
			("ok", None),
		)
		outcome = fx.whatsapp_outcome(made["lead"])
		self.assertEqual(outcome["consent_status"], "Consented")
		self.assertEqual(outcome["records"], [{"basis": "Consent", "private": True}])
		fx.remove_whatsapp()
		self.assertFalse(frappe.db.exists("Lead", made["lead"]))
		self.assertFalse(frappe.db.count("WhatsApp Message", {"lead": made["lead"]}))
		self.assertEqual(settings.get_whatsapp_settings()["configured"], False)
