"""Which WhatsApp provider runs (SOS-P6-11).

The provider is the hidden `provider` field of WhatsApp Settings (empty means Meta's Cloud API). It is in
the database, not in site_config, so every server process sees a change at once. The fake provider runs
only on a site that allows tests, and the live Meta adapter never runs there, so a test can not reach the
real provider (tests give MetaCloudProvider a recorded transport instead). A name with no registered
provider is reported as not available, never as a success.
"""

import json

import frappe
from frappe import _

from sellos.whatsapp.base import (
	InboundMessage,
	ProviderError,
	SentMessage,
	StatusEvent,
	WhatsAppProvider,
)
from sellos.whatsapp.meta import MetaCloudProvider, signature_header

DEFAULT_PROVIDER = "meta"


class FakeWhatsAppProvider(WhatsAppProvider):
	"""A provider for tests and demos. The access token decides the answer:

	* starts with FAKEOK: the connection works,
	* starts with FAKEDOWN: the provider can not be reached,
	* anything else (or a missing token): the token is refused.

	Its webhook body is {"messages": [{"id", "from", "text", "name"}], "statuses": [{"id", "status"}]},
	signed like Meta's (sha256 of the body with the signing secret)."""

	name = "fake"

	def test_connection(self) -> str:
		token = self.access_token or ""
		if token.startswith("FAKEDOWN"):
			raise ProviderError(_("WhatsApp could not be reached. Try again in a few minutes."))
		if not token.startswith("FAKEOK") or not self.phone_number_id:
			raise ProviderError(_("WhatsApp refused this access token. Check the token and the number ID."))
		return _("Connected. WhatsApp accepted the token and the number.")

	def _sent(self, to_number, text) -> SentMessage:
		self.test_connection()
		if not to_number or not (text or "").strip():
			raise ProviderError(_("A number and a message are needed."))
		return SentMessage(message_id=f"fakewa-{frappe.generate_hash(length=12)}", status="sent")

	def send_text(self, to_number: str, body: str) -> SentMessage:
		return self._sent(to_number, body)

	def send_template(self, to_number, template, language, parameters=None) -> SentMessage:
		return self._sent(to_number, template)

	def read_webhook(self, body: bytes) -> list[InboundMessage | StatusEvent]:
		try:
			data = json.loads(body.decode("utf-8"))
		except ValueError:
			raise ProviderError(_("WhatsApp sent an event that could not be read.")) from None
		if not isinstance(data, dict):
			raise ProviderError(_("WhatsApp sent an event that could not be read."))
		events = []
		for message in data.get("messages") or []:
			if message.get("id") and message.get("from"):
				events.append(
					InboundMessage(
						message_id=str(message["id"]),
						from_number=str(message["from"]),
						text=str(message.get("text") or ""),
						name=str(message.get("name") or ""),
						raw={"id": message["id"]},
					)
				)
		for status in data.get("statuses") or []:
			if status.get("id") and status.get("status") in ("sent", "delivered", "read", "failed"):
				events.append(
					StatusEvent(str(status["id"]), status["status"], str(status.get("error") or ""))
				)
		return events


PROVIDERS: dict[str, type[WhatsAppProvider]] = {
	FakeWhatsAppProvider.name: FakeWhatsAppProvider,
	MetaCloudProvider.name: MetaCloudProvider,
}

sign = signature_header  # both providers sign the way Meta does


def get_provider(access_token: str, phone_number_id: str) -> WhatsAppProvider:
	name = frappe.db.get_single_value("WhatsApp Settings", "provider") or DEFAULT_PROVIDER
	provider = PROVIDERS.get(name)
	allow_tests = bool(frappe.conf.get("allow_tests"))
	wrong_site = (name == FakeWhatsAppProvider.name and not allow_tests) or (
		name == MetaCloudProvider.name and allow_tests
	)
	if provider is None or wrong_site:
		raise ProviderError(_("The WhatsApp provider is not available on this site yet."))
	return provider(access_token, phone_number_id)
