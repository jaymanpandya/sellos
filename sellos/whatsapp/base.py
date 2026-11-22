"""The WhatsApp provider interface and its data types (SOS-P6-11).

One interface sits between SellOS and the provider that carries WhatsApp messages, so the provider can
be replaced. Jayman decided on 13 November 2026 that it is Meta's Cloud API, used directly. Each company
connects its own number. The only provider the tests use is the fake one, which never leaves the process
and holds no real key. The agent that builds SellOS never calls the real provider.

Consent never blocks here: an adapter is a transport and never looks at consent. Every send goes through
the consent function (`sellos.crm.consent.check_contact`) before an adapter is called.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sellos.telephony.base import ProviderError

# How far a message has got. A status for an earlier step than the message has reached is out of order.
STATUS_RANK = {"queued": 0, "sent": 1, "delivered": 2, "read": 3, "failed": 3}

__all__ = [
	"STATUS_RANK",
	"InboundMessage",
	"ProviderError",
	"SentMessage",
	"StatusEvent",
	"WhatsAppProvider",
]


@dataclass
class InboundMessage:
	"""A message a customer sent to the company's number. from_number is E.164 with the plus."""

	message_id: str
	from_number: str
	text: str = ""
	name: str = ""
	raw: dict = field(default_factory=dict)


@dataclass
class StatusEvent:
	"""A change in the state of a message the company sent. status is one of STATUS_RANK."""

	message_id: str
	status: str
	error: str = ""


@dataclass
class SentMessage:
	"""The answer to a send: the provider's id for the message and its first status."""

	message_id: str
	status: str = "sent"


class WhatsAppProvider(ABC):
	"""The interface every WhatsApp provider implements (SOS-P6-11).

	* test_connection(): check the token and the number (the Company Admin's Test connection).
	* send_text(to_number, body): send free text, allowed by WhatsApp only inside the 24 hour window.
	* send_template(to_number, template, language, parameters): send an approved template.
	* read_webhook(body): turn a webhook body, whose signature the shared webhook checks have already
	  verified, into a list of InboundMessage and StatusEvent. An unreadable body raises ProviderError.
	* sign(body, secret): the signature header value the provider sends for a body, used by the shared
	  webhook check and by the tests that build signed bodies.

	Every method raises ProviderError, with a message safe to show a person and with no key in it, and
	never any other exception."""

	name = ""

	def __init__(self, access_token: str, phone_number_id: str):
		self.access_token = access_token
		self.phone_number_id = phone_number_id

	@abstractmethod
	def test_connection(self) -> str: ...

	@abstractmethod
	def send_text(self, to_number: str, body: str) -> SentMessage: ...

	@abstractmethod
	def send_template(
		self, to_number: str, template: str, language: str, parameters: list[str] | None = None
	) -> SentMessage: ...

	@abstractmethod
	def read_webhook(self, body: bytes) -> list[InboundMessage | StatusEvent]: ...
