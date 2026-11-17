"""The Plivo adapter (SOS-P2-02).

It places a call with Plivo's Call API, reads Plivo's webhooks into CallEvent and fetches a
recording, and maps every Plivo failure to a clear ProviderError. It talks to Plivo only through
`transport`, one function `(method, url, auth, json_body) -> (status, headers, body_bytes)`, so the
tests run it against recorded Plivo responses and the build agent never calls the real Plivo. The live
transport is `live_transport`, which uses `requests` with a timeout; a connection problem raises
`TransportError`.

Keys come only from Telephony Settings (SOS-P2-01) and are never in a message.
"""

import base64
import hashlib
import hmac
import json
from urllib.parse import urlsplit

from frappe import _

from sellos.telephony.base import (
	CallEvent,
	PlacedCall,
	ProviderError,
	Recording,
	TelephonyProvider,
)

API_ROOT = "https://api.plivo.com/v1"
TIMEOUT_SECONDS = 20
# Plivo's call status words -> ours.
STATE_MAP = {
	"queued": "queued",
	"ringing": "ringing",
	"in-progress": "in-progress",
	"completed": "completed",
	"busy": "busy",
	"no-answer": "no-answer",
	"timeout": "no-answer",
	"failed": "failed",
	"cancel": "cancelled",
	"cancelled": "cancelled",
}


class TransportError(Exception):
	"""Plivo could not be reached (no connection, a timeout)."""


def live_transport(method, url, auth, json_body=None):
	import requests

	try:
		response = requests.request(method, url, auth=auth, json=json_body, timeout=TIMEOUT_SECONDS)
	except requests.RequestException as error:
		raise TransportError(type(error).__name__) from None
	return response.status_code, dict(response.headers), response.content


def _body(raw: bytes) -> dict:
	try:
		data = json.loads(raw.decode("utf-8")) if raw else {}
	except ValueError:
		return {}
	return data if isinstance(data, dict) else {}


def signature_v3(auth_token: str, url: str, params: dict, nonce: str) -> str:
	"""Plivo's V3 signature of a POST webhook: the URL, then the sorted parameters as key and value
	with nothing between, then "." and the nonce, signed with the auth token (HMAC SHA256, base64)."""
	text = url + "".join(f"{key}{params[key]}" for key in sorted(params)) + "." + nonce
	digest = hmac.new(auth_token.encode(), text.encode(), hashlib.sha256).digest()
	return base64.b64encode(digest).decode()


class PlivoProvider(TelephonyProvider):
	name = "plivo"

	def __init__(self, auth_id: str, auth_token: str, transport=None):
		super().__init__(auth_id, auth_token)
		self.transport = transport or live_transport

	# -- plumbing -------------------------------------------------------------------------------

	def _call_api(self, method, url, json_body=None):
		try:
			status, headers, raw = self.transport(method, url, (self.auth_id, self.auth_token), json_body)
		except TransportError:
			raise ProviderError(_("The provider could not be reached. Try again in a few minutes.")) from None
		if 200 <= status < 300:
			return headers, raw
		raise ProviderError(self.error_message(status, _body(raw)))

	def error_message(self, status: int, body: dict) -> str:
		"""Plivo's HTTP status (and its error text, for a rejected request) as a clear message."""
		if status in (401, 403):
			return _("The provider refused these keys. Check the auth ID and the auth token.")
		if status == 404:
			return _("The provider could not find that call or recording.")
		if status == 429:
			return _("The provider is limiting requests. Wait a minute and try again.")
		if status >= 500:
			return _("The provider is having a problem. Try again in a few minutes.")
		reason = str(body.get("error") or body.get("message") or "").strip()
		lowered = reason.lower()
		if "balance" in lowered or "credit" in lowered:
			return _("The provider account has no balance left. Add credit and try again.")
		if "number" in lowered:
			return _("The provider did not accept one of the phone numbers.")
		if reason:
			return _("The provider rejected the request: {0}").format(
				reason[:200].replace(self.auth_token, "***")
			)
		return _("The provider rejected the request.")

	# -- the interface --------------------------------------------------------------------------

	def test_connection(self) -> str:
		self._call_api("GET", f"{API_ROOT}/Account/{self.auth_id}/")
		return _("Connected. The provider accepted the keys.")

	def place_call(
		self, from_number: str, to_number: str, answer_url: str, status_url: str = ""
	) -> PlacedCall:
		if not from_number or not to_number:
			raise ProviderError(_("Both numbers are needed to place a call."))
		if not answer_url.startswith("https://"):
			raise ProviderError(_("The call needs a secure (https) address for the provider to answer on."))
		body = {"from": from_number, "to": to_number, "answer_url": answer_url, "answer_method": "POST"}
		if status_url:
			body.update({"callback_url": status_url, "callback_method": "POST"})
		_headers, raw = self._call_api("POST", f"{API_ROOT}/Account/{self.auth_id}/Call/", body)
		call_id = _body(raw).get("request_uuid")
		if not call_id:
			raise ProviderError(_("The provider did not return a call ID."))
		return PlacedCall(call_id=str(call_id), state="queued")

	def read_webhook(self, payload: dict, url: str = "", headers: dict | None = None) -> list[CallEvent]:
		headers = {key.lower(): value for key, value in (headers or {}).items()}
		self._verify(payload, url, headers)
		call_id = payload.get("CallUUID") or payload.get("call_uuid")
		raw_state = str(payload.get("CallStatus") or "").lower()
		recording_url = payload.get("RecordUrl") or ""
		if not call_id or (raw_state not in STATE_MAP and not recording_url):
			raise ProviderError(_("The provider sent an event that could not be read."))
		state = STATE_MAP.get(raw_state, "completed")
		return [
			CallEvent(
				call_id=str(call_id),
				state=state,
				from_number=payload.get("From", ""),
				to_number=payload.get("To", ""),
				duration=_seconds(payload.get("Duration") or payload.get("RecordingDuration")),
				recording_url=recording_url,
				raw=dict(payload),
			)
		]

	def _verify(self, payload: dict, url: str, headers: dict):
		signature = headers.get("x-plivo-signature-v3")
		nonce = headers.get("x-plivo-signature-v3-nonce")
		if not signature or not nonce or not url:
			raise ProviderError(_("The provider's signature is missing, so the event was not accepted."))
		expected = signature_v3(self.auth_token, url, payload, nonce)
		if not hmac.compare_digest(expected, signature.strip()):
			raise ProviderError(_("The provider's signature did not match, so the event was not accepted."))

	def fetch_recording(self, recording_url: str) -> Recording:
		parts = urlsplit(recording_url or "")
		# The keys go only to Plivo: refuse any other host before sending them.
		if parts.scheme != "https" or not (parts.hostname or "").endswith(".plivo.com"):
			raise ProviderError(_("The recording address is not a provider address."))
		headers, raw = self._call_api("GET", recording_url)
		if not raw:
			raise ProviderError(_("The recording was empty."))
		content_type = {k.lower(): v for k, v in headers.items()}.get("content-type", "audio/mpeg")
		return Recording(content=raw, content_type=content_type)


def _seconds(value) -> int:
	try:
		return int(float(value))
	except (TypeError, ValueError):
		return 0


__all__ = ["PlivoProvider", "TransportError", "live_transport", "signature_v3"]
