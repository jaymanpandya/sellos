"""Meta's WhatsApp Cloud API adapter (SOS-P6-11).

It sends text and template messages through the Graph API, reads Meta's webhook bodies into
InboundMessage and StatusEvent, and maps every Meta failure to a clear ProviderError. It talks to Meta
only through `transport`, one function `(method, url, token, json_body) -> (status, body_bytes)`, so the
tests run it against recorded Meta answers and the build agent never calls the real Meta. The live
transport uses `requests` with a timeout.

The access token comes only from WhatsApp Settings and is never in a message. Meta signs a webhook body
with the app secret: `X-Hub-Signature-256: sha256=<hex hmac of the raw body>`.
"""

import hashlib
import hmac
import json

from frappe import _

from sellos.whatsapp.base import (
	InboundMessage,
	ProviderError,
	SentMessage,
	StatusEvent,
	WhatsAppProvider,
)

GRAPH_ROOT = "https://graph.facebook.com/v21.0"
TIMEOUT_SECONDS = 20
SIGNATURE_PREFIX = "sha256="


class TransportError(Exception):
	"""Meta could not be reached (no connection, a timeout)."""


def live_transport(method, url, token, json_body=None):
	import requests

	try:
		response = requests.request(
			method,
			url,
			headers={"Authorization": f"Bearer {token}"},
			json=json_body,
			timeout=TIMEOUT_SECONDS,
		)
	except requests.RequestException as error:
		raise TransportError(type(error).__name__) from None
	return response.status_code, response.content


def signature_header(body: bytes, secret: str) -> str:
	"""The X-Hub-Signature-256 value for a body."""
	return SIGNATURE_PREFIX + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _json(raw: bytes) -> dict:
	try:
		data = json.loads(raw.decode("utf-8")) if raw else {}
	except ValueError:
		return {}
	return data if isinstance(data, dict) else {}


def e164_digits(number: str) -> str:
	"""Meta wants the number as digits with the country code and no plus."""
	return "".join(ch for ch in str(number or "") if ch.isdigit())


class MetaCloudProvider(WhatsAppProvider):
	name = "meta"

	def __init__(self, access_token: str, phone_number_id: str, transport=None):
		super().__init__(access_token, phone_number_id)
		self.transport = transport or live_transport

	def _call(self, method, path, body=None) -> dict:
		try:
			status, raw = self.transport(method, f"{GRAPH_ROOT}/{path}", self.access_token, body)
		except TransportError:
			raise ProviderError(_("WhatsApp could not be reached. Try again in a few minutes.")) from None
		if 200 <= status < 300:
			return _json(raw)
		raise ProviderError(self.error_message(status, _json(raw)))

	def error_message(self, status: int, body: dict) -> str:
		error = body.get("error") if isinstance(body.get("error"), dict) else {}
		code = error.get("code")
		if status in (401, 403) or code in (190, 10):
			return _("WhatsApp refused this access token. Check the token and the number ID.")
		if code == 131047:
			return _("The 24 hour window has closed. Send an approved template instead.")
		if code in (131026, 131021):
			return _("WhatsApp could not deliver to this number. It may not be on WhatsApp.")
		if code in (132000, 132001, 132005, 132012):
			return _("WhatsApp did not accept this template. Check its name, language and approval.")
		if status == 429 or code in (4, 80007, 130429):
			return _("WhatsApp is limiting messages. Wait a minute and try again.")
		if status >= 500:
			return _("WhatsApp is having a problem. Try again in a few minutes.")
		reason = str(error.get("message") or "").strip()
		if reason:
			return _("WhatsApp rejected the message: {0}").format(
				reason[:200].replace(self.access_token or "\0", "***")
			)
		return _("WhatsApp rejected the message.")

	def test_connection(self) -> str:
		self._call("GET", f"{self.phone_number_id}?fields=display_phone_number")
		return _("Connected. WhatsApp accepted the token and the number.")

	def _send(self, payload) -> SentMessage:
		answer = self._call("POST", f"{self.phone_number_id}/messages", payload)
		messages = answer.get("messages")
		message_id = messages[0].get("id") if isinstance(messages, list) and messages else None
		if not message_id:
			raise ProviderError(_("WhatsApp did not return a message ID."))
		return SentMessage(message_id=str(message_id), status="sent")

	def send_text(self, to_number: str, body: str) -> SentMessage:
		if not e164_digits(to_number) or not (body or "").strip():
			raise ProviderError(_("A number and a message are needed."))
		return self._send(
			{
				"messaging_product": "whatsapp",
				"to": e164_digits(to_number),
				"type": "text",
				"text": {"body": body},
			}
		)

	def send_template(self, to_number, template, language, parameters=None) -> SentMessage:
		if not e164_digits(to_number) or not template:
			raise ProviderError(_("A number and a template are needed."))
		content = {"name": template, "language": {"code": language or "en"}}
		if parameters:
			content["components"] = [
				{"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in parameters]}
			]
		return self._send(
			{
				"messaging_product": "whatsapp",
				"to": e164_digits(to_number),
				"type": "template",
				"template": content,
			}
		)

	def read_webhook(self, body: bytes) -> list[InboundMessage | StatusEvent]:
		data = _json(body)
		if data.get("object") != "whatsapp_business_account":
			raise ProviderError(_("WhatsApp sent an event that could not be read."))
		events = []
		for entry in data.get("entry") or []:
			for change in (entry or {}).get("changes") or []:
				value = (change or {}).get("value") or {}
				meta = value.get("metadata") or {}
				if self.phone_number_id and meta.get("phone_number_id") not in (None, self.phone_number_id):
					continue  # an event for another number of the same Meta account
				names = {
					str(c.get("wa_id")): (c.get("profile") or {}).get("name", "")
					for c in value.get("contacts") or []
				}
				for message in value.get("messages") or []:
					sender = str(message.get("from") or "")
					if not message.get("id") or not sender:
						continue
					events.append(
						InboundMessage(
							message_id=str(message["id"]),
							from_number="+" + e164_digits(sender),
							text=_text_of(message),
							name=names.get(sender, ""),
							raw={
								"id": message["id"],
								"type": message.get("type"),
								"timestamp": message.get("timestamp"),
							},
						)
					)
				for status in value.get("statuses") or []:
					if status.get("id") and status.get("status") in ("sent", "delivered", "read", "failed"):
						errors = status.get("errors") or [{}]
						events.append(
							StatusEvent(
								message_id=str(status["id"]),
								status=status["status"],
								error=str((errors[0] or {}).get("title") or "")[:200],
							)
						)
		return events


def _text_of(message: dict) -> str:
	kind = message.get("type")
	if kind == "text":
		return str((message.get("text") or {}).get("body") or "")
	if kind == "button":
		return str((message.get("button") or {}).get("text") or "")
	if kind == "interactive":
		reply = message.get("interactive") or {}
		picked = reply.get("button_reply") or reply.get("list_reply") or {}
		return str(picked.get("title") or "")
	return ""
