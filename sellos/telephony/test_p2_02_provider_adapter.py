"""SOS-P2-02: the provider adapter. The interface is documented; the Plivo adapter places a call and
reads its events against recorded Plivo responses; the fake provider answers the same interface;
provider errors map to clear messages with no key in them. The live test call is SOS-P2-02L."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.telephony import base, plivo, provider
from sellos.telephony.base import CallEvent, PlacedCall, ProviderError, Recording, TelephonyProvider
from sellos.telephony.plivo import PlivoProvider, TransportError, signature_v3
from sellos.tests import phones

AUTH_ID = "MAFAKEPLIVO0A1B2C3D"
AUTH_TOKEN = "tokenvalue7f3a9c1e5b2d4f68"
FROM = phones.in_mobile(2301)
TO = phones.in_mobile(2302)
ANSWER = "https://acme.sellos.example/api/method/answer"
STATUS = "https://acme.sellos.example/api/method/status"
CALL_URL = f"{plivo.API_ROOT}/Account/{AUTH_ID}/Call/"
RECORDING = "https://media.plivo.com/v1/Account/recordings/abc.mp3"
CALL_ID = "e2f1a7c4-5b6d-4c1e-9a0b-3d2f1e0c9b8a"

# Responses recorded from Plivo's documented replies.
CALL_CREATED = (
	201,
	{},
	json.dumps(
		{"api_id": "a1", "message": "call fulfilled", "request_uuid": CALL_ID},
	).encode(),
)
ACCOUNT_OK = (200, {}, json.dumps({"account_type": "standard", "auth_id": AUTH_ID}).encode())


def reply(status, **body):
	return status, {}, json.dumps(body).encode()


class Recorded:
	"""A transport that returns recorded responses and remembers the requests."""

	def __init__(self, response=None, error=None):
		self.response, self.error, self.requests = response, error, []

	def __call__(self, method, url, auth, json_body=None):
		self.requests.append((method, url, auth, json_body))
		if self.error:
			raise self.error
		return self.response


def adapter(response=None, error=None):
	transport = Recorded(response, error)
	return PlivoProvider(AUTH_ID, AUTH_TOKEN, transport=transport), transport


def signed(payload, url=STATUS, nonce="n0nce-1"):
	headers = {
		"X-Plivo-Signature-V3": signature_v3(AUTH_TOKEN, url, payload, nonce),
		"X-Plivo-Signature-V3-Nonce": nonce,
	}
	return headers


COMPLETED = {
	"CallUUID": CALL_ID,
	"CallStatus": "completed",
	"From": FROM,
	"To": TO,
	"Duration": "42",
}


class TestProviderInterface(IntegrationTestCase):
	"""SOS-P2-02: the interface is documented and both providers answer it."""

	def test_interface_is_documented(self):
		self.assertIn("place_call", TelephonyProvider.__doc__)
		self.assertIn("read_webhook", TelephonyProvider.__doc__)
		self.assertIn("fetch_recording", TelephonyProvider.__doc__)
		for method in ("test_connection", "place_call", "read_webhook", "fetch_recording"):
			self.assertTrue(getattr(TelephonyProvider, method).__doc__, method)
			self.assertIn(method, TelephonyProvider.__abstractmethods__)

	def test_provider_module_reexports_the_interface(self):
		self.assertIs(provider.TelephonyProvider, base.TelephonyProvider)
		self.assertIs(provider.ProviderError, base.ProviderError)
		self.assertIs(provider.PROVIDERS["plivo"], PlivoProvider)
		self.assertTrue(issubclass(provider.FakeProvider, TelephonyProvider))
		self.assertTrue(issubclass(PlivoProvider, TelephonyProvider))

	def test_fake_provider_answers_the_whole_interface(self):
		fake = provider.FakeProvider("FAKEOK1", AUTH_TOKEN)
		placed = fake.place_call(FROM, TO, ANSWER)
		self.assertIsInstance(placed, PlacedCall)
		self.assertTrue(placed.call_id)
		events = fake.read_webhook({"call_id": placed.call_id, "state": "completed", "duration": 9})
		self.assertEqual(
			(events[0].call_id, events[0].state, events[0].duration), (placed.call_id, "completed", 9)
		)
		self.assertIsInstance(fake.fetch_recording(RECORDING), Recording)

	def test_fake_provider_errors_are_clear(self):
		with self.assertRaises(ProviderError):
			provider.FakeProvider("WRONG", AUTH_TOKEN).place_call(FROM, TO, ANSWER)
		with self.assertRaises(ProviderError):
			provider.FakeProvider("FAKEOK1", AUTH_TOKEN).read_webhook({"call_id": "x", "state": "weird"})
		with self.assertRaises(ProviderError):
			provider.FakeProvider("FAKEDOWN1", AUTH_TOKEN).fetch_recording(RECORDING)

	def test_get_provider_picks_plivo_only_off_test_sites(self):
		self.addCleanup(frappe.db.rollback)
		frappe.db.set_single_value("Telephony Settings", "provider", "")
		with patch.dict(frappe.local.conf, {"allow_tests": 0}):
			self.assertIsInstance(provider.get_provider(AUTH_ID, AUTH_TOKEN), PlivoProvider)
		with patch.dict(frappe.local.conf, {"allow_tests": 1}):
			with self.assertRaises(ProviderError) as caught:
				provider.get_provider(AUTH_ID, AUTH_TOKEN)
		self.assertIn("not available", str(caught.exception))


class TestPlivoPlaceCall(IntegrationTestCase):
	"""SOS-P2-02: place a call against recorded Plivo responses."""

	def test_places_a_call_and_reads_its_id(self):
		plivo_provider, transport = adapter(CALL_CREATED)
		placed = plivo_provider.place_call(FROM, TO, ANSWER, STATUS)
		self.assertEqual(placed, PlacedCall(call_id=CALL_ID, state="queued"))
		method, url, auth, body = transport.requests[0]
		self.assertEqual((method, url, auth), ("POST", CALL_URL, (AUTH_ID, AUTH_TOKEN)))
		self.assertEqual((body["from"], body["to"], body["answer_url"]), (FROM, TO, ANSWER))
		self.assertEqual(body["callback_url"], STATUS)

	def test_no_status_url_sends_no_callback(self):
		plivo_provider, transport = adapter(CALL_CREATED)
		plivo_provider.place_call(FROM, TO, ANSWER)
		self.assertNotIn("callback_url", transport.requests[0][3])

	def test_input_problems_never_reach_plivo(self):
		plivo_provider, transport = adapter(CALL_CREATED)
		for args in ((FROM, "", ANSWER), ("", TO, ANSWER), (FROM, TO, "http://insecure.example/a")):
			with self.assertRaises(ProviderError):
				plivo_provider.place_call(*args)
		self.assertEqual(transport.requests, [])

	def test_a_reply_without_a_call_id_is_an_error(self):
		plivo_provider, _transport = adapter(reply(201, message="call fulfilled"))
		with self.assertRaises(ProviderError) as caught:
			plivo_provider.place_call(FROM, TO, ANSWER)
		self.assertIn("call ID", str(caught.exception))

	def test_test_connection_reads_the_account(self):
		plivo_provider, transport = adapter(ACCOUNT_OK)
		self.assertIn("Connected", plivo_provider.test_connection())
		self.assertEqual(transport.requests[0][:2], ("GET", f"{plivo.API_ROOT}/Account/{AUTH_ID}/"))


class TestPlivoErrors(IntegrationTestCase):
	"""SOS-P2-02: provider errors map to clear messages, with no key in them."""

	def message(self, response=None, error=None):
		plivo_provider, _transport = adapter(response, error)
		with self.assertRaises(ProviderError) as caught:
			plivo_provider.place_call(FROM, TO, ANSWER)
		return str(caught.exception)

	def test_each_status_has_its_message(self):
		self.assertIn(
			"refused these keys", self.message(reply(401, error="Authentication credentials invalid"))
		)
		self.assertIn("refused these keys", self.message(reply(403)))
		self.assertIn("could not find", self.message(reply(404)))
		self.assertIn("limiting requests", self.message(reply(429)))
		self.assertIn("having a problem", self.message(reply(503)))
		self.assertIn("could not be reached", self.message(error=TransportError("Timeout")))

	def test_rejected_requests_say_why(self):
		self.assertIn("no balance", self.message(reply(400, error="Insufficient credit balance")))
		self.assertIn("phone numbers", self.message(reply(400, error="to number is invalid")))
		self.assertIn(
			"rejected the request: bad answer_url", self.message(reply(400, error="bad answer_url"))
		)
		self.assertEqual(self.message((400, {}, b"not json")), "The provider rejected the request.")

	def test_no_key_appears_in_a_message(self):
		leaky = self.message(reply(400, error=f"token {AUTH_TOKEN} rejected"))
		self.assertNotIn(AUTH_TOKEN, leaky)
		self.assertIn("***", leaky)
		self.assertNotIn(AUTH_ID, self.message(error=TransportError("Timeout")))


class TestPlivoWebhook(IntegrationTestCase):
	"""SOS-P2-02: read Plivo's webhook events, checking its signature."""

	def read(self, payload, headers=None, url=STATUS):
		return adapter()[0].read_webhook(payload, url, signed(payload, url) if headers is None else headers)

	def test_reads_a_completed_call(self):
		(event,) = self.read(COMPLETED)
		self.assertEqual(
			(event.call_id, event.state, event.from_number, event.to_number, event.duration),
			(CALL_ID, "completed", FROM, TO, 42),
		)
		self.assertIsInstance(event, CallEvent)
		self.assertEqual(event.raw, COMPLETED)

	def test_provider_states_become_ours(self):
		expected = {
			"ringing": "ringing",
			"in-progress": "in-progress",
			"busy": "busy",
			"no-answer": "no-answer",
			"timeout": "no-answer",
			"failed": "failed",
			"cancel": "cancelled",
		}
		for theirs, ours in expected.items():
			(event,) = self.read({**COMPLETED, "CallStatus": theirs})
			self.assertEqual(event.state, ours, theirs)
			self.assertIn(event.state, base.CALL_STATES)

	def test_reads_a_recording_event(self):
		payload = {"CallUUID": CALL_ID, "RecordUrl": RECORDING, "RecordingDuration": "40"}
		(event,) = self.read(payload)
		self.assertEqual((event.recording_url, event.duration, event.state), (RECORDING, 40, "completed"))

	def test_a_bad_or_missing_signature_is_refused(self):
		for headers in (
			{"X-Plivo-Signature-V3": "AAAA", "X-Plivo-Signature-V3-Nonce": "n0nce-1"},
			{"x-plivo-signature-v3-nonce": "n0nce-1"},
			{},
		):
			with self.assertRaises(ProviderError) as caught:
				self.read(COMPLETED, headers)
			self.assertIn("signature", str(caught.exception))
		with self.assertRaises(ProviderError):
			self.read(COMPLETED, signed(COMPLETED), url="https://other.example/x")

	def test_header_names_are_case_insensitive(self):
		headers = {key.lower(): value for key, value in signed(COMPLETED).items()}
		self.assertEqual(self.read(COMPLETED, headers)[0].call_id, CALL_ID)

	def test_an_unreadable_event_is_an_error(self):
		for payload in ({"CallStatus": "completed"}, {"CallUUID": CALL_ID, "CallStatus": "weird"}):
			with self.assertRaises(ProviderError) as caught:
				self.read(payload)
			self.assertIn("could not be read", str(caught.exception))


class TestPlivoRecording(IntegrationTestCase):
	"""SOS-P2-02: fetch a recording, sending the keys only to Plivo."""

	def test_fetches_a_recording(self):
		plivo_provider, transport = adapter((200, {"Content-Type": "audio/wav"}, b"RIFFdata"))
		recording = plivo_provider.fetch_recording(RECORDING)
		self.assertEqual((recording.content, recording.content_type), (b"RIFFdata", "audio/wav"))
		self.assertEqual(transport.requests[0][:3], ("GET", RECORDING, (AUTH_ID, AUTH_TOKEN)))

	def test_other_hosts_never_get_the_keys(self):
		plivo_provider, transport = adapter((200, {}, b"x"))
		for url in (
			"https://evil.example/a.mp3",
			"http://media.plivo.com/a.mp3",
			"",
			"https://plivo.com.evil.example/a",
		):
			with self.assertRaises(ProviderError):
				plivo_provider.fetch_recording(url)
		self.assertEqual(transport.requests, [])

	def test_missing_and_empty_recordings_are_errors(self):
		with self.assertRaises(ProviderError) as caught:
			adapter(reply(404))[0].fetch_recording(RECORDING)
		self.assertIn("could not find", str(caught.exception))
		with self.assertRaises(ProviderError) as caught:
			adapter((200, {}, b""))[0].fetch_recording(RECORDING)
		self.assertIn("empty", str(caught.exception))


class TestLiveTransport(IntegrationTestCase):
	"""SOS-P2-02: the live transport turns a connection failure into TransportError (no real call)."""

	def test_connection_failure_becomes_transport_error(self):
		import requests

		with patch("requests.request", side_effect=requests.ConnectionError("boom")):
			with self.assertRaises(TransportError):
				plivo.live_transport("GET", CALL_URL, (AUTH_ID, AUTH_TOKEN))
