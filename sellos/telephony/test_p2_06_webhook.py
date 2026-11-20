"""SOS-P2-06: the Plivo webhook. A valid event updates the Call Log; an invalid signature writes and
reveals nothing; a replayed or out of order event changes nothing; an oversized or rate limited request
is refused; the recording is fetched after the call; the signing secret is never in a log. Tests use a
fake signing key and Plivo shaped event bodies, and call the endpoint with a built request."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from sellos.access import webhooks
from sellos.access.roles import ensure_roles
from sellos.crm.test_crm import CrmCase
from sellos.telephony import call_log, webhook
from sellos.telephony.plivo import signature_v3
from sellos.telephony.settings import save_telephony_settings
from sellos.testing.users import create_test_users
from sellos.tests import phones

SECRET = "p206-fake-signing-key-5c1d9e"
RECORDING = "https://media.plivo.com/v1/Account/recordings/p206.mp3"
LANDLINE = f"{phones.in_mobile(3600)[:3]}22{phones.in_mobile(3600)[-8:]}"
PATH = "/api/method/sellos.telephony.webhook.plivo_call_event"
BASE = "https://tenant.example"
METHOD = "sellos.telephony.webhook.plivo_call_event"


def call_endpoint(params, secret=SECRET, nonce=None, signature=None, headers=None, data=None):
	"""Call the webhook as Plivo does: a signed form post, as a guest."""
	url = BASE + PATH
	sent = {"X-Plivo-Signature-V3-Nonce": nonce} if nonce else {}
	if nonce and signature is None:
		signature = signature_v3(secret, url, params, nonce)
	if signature:
		sent["X-Plivo-Signature-V3"] = signature
	sent.update(headers or {})
	environ = EnvironBuilder(method="POST", path=PATH, base_url=BASE, data=data or params, headers=sent)
	frappe.local.request = Request(environ.get_environ())
	frappe.local.response = frappe._dict()
	frappe.set_user("Guest")
	try:
		message = webhook.plivo_call_event()
	finally:
		frappe.set_user("Administrator")
	return message, frappe.local.response.get("http_status_code")


class WebhookCase(CrmCase):
	def setUp(self):
		ensure_roles()
		create_test_users()
		_, self.lead = self.make_lead()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		frappe.db.set_single_value("Telephony Settings", "provider", "fake")
		save_telephony_settings("FAKEOK1", SECRET, LANDLINE)
		self.log = call_log.place_logged_call(self.lead, "Service")["log"]
		self.call_id = frappe.db.get_value("Call Log", self.log, "call_id")
		self.nonce_count = 0
		frappe.cache.delete_keys("sellos_webhook_rate")
		patcher = patch("sellos.telephony.webhook.frappe.enqueue")
		self.enqueue = patcher.start()
		self.addCleanup(patcher.stop)

	def nonce(self):
		self.nonce_count += 1
		return f"nonce-{self.log}-{self.nonce_count}"

	def event(self, status, **extra):
		params = {"CallUUID": self.call_id, "CallStatus": status, **extra}
		return call_endpoint(params, nonce=self.nonce())

	def row(self):
		return frappe.db.get_value(
			"Call Log",
			self.log,
			["state", "duration", "billed_duration", "hangup_cause", "recording_link"],
			as_dict=True,
		)

	def writes(self):
		return (self.row(), frappe.db.count("Webhook Event"))


class TestRegistration(IntegrationTestCase):
	"""SOS-P2-06: the endpoint is a registered provider webhook that declares every check."""

	def test_it_is_registered_with_every_check_and_allows_guests(self):
		checks = webhooks.declared_webhooks()[METHOD]
		for name in ("signature", "replay", "max_body_bytes", "rate_limit_per_tenant", "secret_setting"):
			self.assertTrue(checks[name], name)
		self.assertEqual(checks["secret_setting"], "Telephony Settings.auth_token")
		self.assertIn(webhook.plivo_call_event, frappe.guest_methods)

	def test_the_request_guard_lets_it_through_and_still_refuses_an_undeclared_method(self):
		from sellos.access.registry import is_refused, undeclared_whitelisted_methods

		self.assertFalse(is_refused(METHOD))
		self.assertTrue(is_refused("sellos.telephony.webhook.not_a_webhook"))
		self.assertNotIn(METHOD, undeclared_whitelisted_methods())

	def test_a_webhook_without_its_checks_cannot_be_registered(self):
		with self.assertRaises(ValueError):
			webhooks.provider_webhook(
				provider="x",
				signature=webhook.verify_plivo_signature,
				replay="",
				max_body_bytes=10,
				rate_limit_per_tenant=1,
				secret_setting="Telephony Settings.auth_token",
			)


class TestValidEvents(WebhookCase):
	"""SOS-P2-06: valid events update the log."""

	def test_ringing_answer_and_hangup_update_the_log(self):
		self.assertEqual(self.event("ringing"), ("ok", None))
		self.assertEqual(self.row().state, "ringing")
		self.event("in-progress")
		self.assertEqual(self.row().state, "in-progress")
		self.assertEqual(
			self.event("completed", Duration="61", HangupCauseName="Normal Hangup"), ("ok", None)
		)
		row = self.row()
		self.assertEqual(
			(row.state, row.duration, row.billed_duration, row.hangup_cause),
			("completed", 61, 120, "Normal Hangup"),
		)

	def test_the_recording_link_is_stored_and_fetched_after_the_call(self):
		self.event("completed", Duration="30")
		self.event("completed", RecordUrl=RECORDING, RecordingDuration="30")
		self.assertEqual(self.row().recording_link, RECORDING)
		self.assertEqual(self.row().state, "completed")
		self.enqueue.assert_called_once()
		self.assertEqual(self.enqueue.call_args.kwargs["log"], self.log)
		self.assertTrue(self.enqueue.call_args.kwargs["enqueue_after_commit"])
		file = webhook.fetch_recording(self.log)
		attached = frappe.db.get_value(
			"File", file, ["attached_to_doctype", "attached_to_name", "is_private"]
		)
		self.assertEqual(tuple(attached), ("Call Log", self.log, 1))
		self.assertEqual(webhook.fetch_recording(self.log), file)

	def test_a_busy_call_keeps_busy_when_its_recording_event_says_completed(self):
		self.event("busy", Duration="0")
		self.event("completed", RecordUrl=RECORDING)
		self.assertEqual((self.row().state, self.row().recording_link), ("busy", RECORDING))

	def test_a_failed_fetch_is_logged_without_the_key_and_does_not_raise(self):
		frappe.db.set_value("Call Log", self.log, "recording_link", "")
		self.assertIsNone(webhook.fetch_recording(self.log))
		frappe.db.set_value("Call Log", self.log, "recording_link", RECORDING)
		frappe.db.set_single_value("Telephony Settings", "provider", "plivo")
		self.assertIsNone(webhook.fetch_recording(self.log))
		message = frappe.get_all("Error Log", filters={"method": ["like", "Call recording%"]}, pluck="error")
		self.assertTrue(message)
		self.assertFalse(any(SECRET in text for text in message))

	def test_an_unknown_call_writes_nothing_to_any_log(self):
		before = frappe.db.count("Call Log")
		call_endpoint({"CallUUID": "no-such-call", "CallStatus": "completed"}, nonce=self.nonce())
		self.assertEqual(frappe.db.count("Call Log"), before)
		self.assertEqual(self.row().state, "queued")

	def test_an_unreadable_but_signed_event_is_ignored(self):
		self.assertEqual(call_endpoint({"Hello": "there"}, nonce=self.nonce()), ("ignored", None))


class TestInvalidSignature(WebhookCase):
	"""SOS-P2-06: an invalid or missing signature writes nothing and reveals nothing."""

	def assert_refused(self, result):
		self.assertEqual(result, ("refused", 403))

	def test_every_kind_of_bad_signature_gets_the_same_answer_and_writes_nothing(self):
		before = self.writes()
		params = {"CallUUID": self.call_id, "CallStatus": "completed", "Duration": "9"}
		answers = [
			call_endpoint(params, nonce=self.nonce(), signature="bm90IHJpZ2h0"),
			call_endpoint(params, nonce=self.nonce(), secret="another-key"),
			call_endpoint(params),  # no signature, no nonce
			call_endpoint(params, nonce=self.nonce(), signature=" "),
			call_endpoint(params, signature="c2lnbmVkLXdpdGhvdXQtbm9uY2U="),
		]
		for answer in answers:
			self.assert_refused(answer)
		self.assertEqual(self.writes(), before)

	def test_a_tampered_body_is_refused(self):
		params = {"CallUUID": self.call_id, "CallStatus": "ringing"}
		nonce = self.nonce()
		signature = signature_v3(SECRET, BASE + PATH, params, nonce)
		before = self.writes()
		self.assert_refused(
			call_endpoint(
				params, nonce=nonce, signature=signature, data={**params, "CallStatus": "completed"}
			)
		)
		self.assertEqual(self.writes(), before)

	def test_with_no_secret_saved_every_request_is_refused(self):
		frappe.db.set_single_value("Telephony Settings", "auth_token", "")
		frappe.db.delete("__Auth", {"doctype": "Telephony Settings", "fieldname": "auth_token"})
		before = self.writes()
		self.assert_refused(self.event("completed"))
		self.assertEqual(self.writes(), before)

	def test_the_tenant_is_the_site_not_the_request(self):
		params = {"CallUUID": self.call_id, "CallStatus": "completed", "tenant": "other"}
		_message, status = call_endpoint(
			params, nonce=self.nonce(), headers={"X-Tenant": "other", "Host": "other.example"}
		)
		self.assertEqual(status, 403)  # signed for another host name
		self.assertEqual(self.row().state, "queued")


class TestReplayAndOrder(WebhookCase):
	"""SOS-P2-06: replayed events change nothing and out of order events are ignored."""

	def test_a_replayed_event_changes_nothing(self):
		params = {"CallUUID": self.call_id, "CallStatus": "completed", "Duration": "61"}
		nonce = self.nonce()
		self.assertEqual(call_endpoint(params, nonce=nonce), ("ok", None))
		first = self.writes()
		frappe.db.set_value("Call Log", self.log, "duration", 5)  # a later edit a replay must not undo
		self.assertEqual(call_endpoint(params, nonce=nonce), ("ignored", None))
		self.assertEqual(self.writes()[1], first[1])
		self.assertEqual(self.row().duration, 5)

	def test_a_late_ringing_never_undoes_a_hangup(self):
		self.event("completed", Duration="12")
		self.event("ringing")
		self.event("in-progress")
		self.assertEqual((self.row().state, self.row().duration), ("completed", 12))

	def test_an_earlier_step_after_a_later_one_is_ignored(self):
		self.event("in-progress")
		self.event("ringing")
		self.assertEqual(self.row().state, "in-progress")

	def test_a_second_ending_does_not_replace_the_first(self):
		self.event("completed", Duration="12")
		self.event("failed", Duration="0")
		self.assertEqual((self.row().state, self.row().duration), ("completed", 12))

	def test_replays_are_remembered_for_this_tenant_only_by_its_own_table(self):
		self.assertTrue(webhooks.remember_event("plivo", "key-p206"))
		self.assertFalse(webhooks.remember_event("plivo", "key-p206"))
		self.assertTrue(webhooks.remember_event("other-provider", "key-p206"))


class TestBodyCapAndRate(WebhookCase):
	"""SOS-P2-06: an oversized body and a flood are refused before any work."""

	def test_an_oversized_body_is_refused_and_writes_nothing(self):
		before = self.writes()
		big = {"CallUUID": self.call_id, "CallStatus": "completed", "pad": "x" * webhook.MAX_BODY_BYTES}
		self.assertEqual(call_endpoint(big, nonce=self.nonce()), ("too large", 413))
		self.assertEqual(self.writes(), before)

	def test_the_cap_is_checked_from_the_declared_length_before_the_body_is_read(self):
		with patch.object(Request, "get_data", side_effect=AssertionError("body was read")):
			params = {"CallUUID": self.call_id, "CallStatus": "completed"}
			environ = EnvironBuilder(method="POST", path=PATH, base_url=BASE, data=params).get_environ()
			environ["CONTENT_LENGTH"] = str(webhook.MAX_BODY_BYTES + 1)
			frappe.local.request = Request(environ)
			frappe.local.response = frappe._dict()
			self.assertEqual(webhook.plivo_call_event(), "too large")

	def test_requests_over_the_limit_are_refused_and_write_nothing(self):
		with patch("sellos.access.webhooks.time.time", return_value=1_700_000_000):
			for _count in range(webhook.REQUESTS_PER_MINUTE):
				self.assertFalse(webhooks.over_rate_limit(METHOD, webhook.REQUESTS_PER_MINUTE, 1_700_000_000))
			before = self.writes()
			self.assertEqual(self.event("completed", Duration="3"), ("rate limited", 429))
			self.assertEqual(self.writes(), before)
		# the next minute starts a new count
		self.assertFalse(webhooks.over_rate_limit(METHOD, 1, 1_700_000_000 + 120))


class TestSecretNeverLogged(WebhookCase):
	"""SOS-P2-06: the signing secret is in no log, answer, error or stored row."""

	def test_the_secret_appears_nowhere_after_good_and_bad_requests(self):
		answers = [
			self.event("ringing"),
			call_endpoint({"CallUUID": self.call_id}, nonce=self.nonce(), secret="wrong-key"),
			call_endpoint({"CallUUID": self.call_id, "CallStatus": "completed"}),
		]
		with patch("frappe.logger") as logger:
			self.event("completed", Duration="4")
		self.assertFalse(logger.called)
		self.assertNotIn(SECRET, repr(answers))
		self.assertFalse([e for e in frappe.get_all("Error Log", pluck="error") if SECRET in e])
		for doctype in ("Webhook Event", "Call Log", "Version", "Activity Log"):
			rows = frappe.get_all(doctype, fields=["*"])
			self.assertNotIn(SECRET, repr(rows), doctype)
