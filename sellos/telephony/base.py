"""The telephony provider interface and its data types (SOS-P2-02). provider.py re-exports them."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(Exception):
	"""A provider failure with a message that is safe to show to a person (it never holds a key)."""


# The call states every adapter reports, whatever the provider calls them.
CALL_STATES = ("queued", "ringing", "in-progress", "completed", "busy", "no-answer", "failed", "cancelled")


@dataclass
class PlacedCall:
	"""The answer to place_call: the provider's id for the call and its first state."""

	call_id: str
	state: str = "queued"


@dataclass
class CallEvent:
	"""One event read from a provider webhook, in SellOS's own words (SOS-P2-02).

	state is one of CALL_STATES. duration is in seconds. recording_url is set only on an event that
	says a recording is ready. raw is the provider's payload, kept for the call log and never shown.
	"""

	call_id: str
	state: str
	from_number: str = ""
	to_number: str = ""
	duration: int = 0
	recording_url: str = ""
	raw: dict = field(default_factory=dict)
	# "inbound" for a call made to our number (a missed call is one that ends unanswered), else "".
	direction: str = ""


@dataclass
class Recording:
	"""A fetched recording: its bytes and content type."""

	content: bytes
	content_type: str = "audio/mpeg"


class TelephonyProvider(ABC):
	"""The interface every calling provider implements (SOS-P2-02).

	* test_connection(): check the keys (SOS-P2-01).
	* place_call(from_number, to_number, answer_url, status_url=""): ring `from_number` or `to_number`
	  as the provider's flow says, and return a PlacedCall. Numbers are E.164 with the plus.
	* read_webhook(payload, url="", headers=None): check the provider's signature when the provider
	  signs, and return the list of CallEvent in the payload. A bad signature raises ProviderError.
	* fetch_recording(recording_url): return the Recording.

	Every method raises ProviderError, with a message safe to show a person and with no key in it,
	and never any other exception: an adapter maps what its provider says to a clear message. Consent
	never blocks here: an adapter does not look at consent (SOS-P2-02 is a transport, not a check).
	"""

	name = ""

	def __init__(self, auth_id: str, auth_token: str):
		self.auth_id = auth_id
		self.auth_token = auth_token

	@abstractmethod
	def test_connection(self) -> str:
		"""Check the keys with the provider. Return a short message on success, raise ProviderError
		with a clear message otherwise."""

	@abstractmethod
	def place_call(
		self, from_number: str, to_number: str, answer_url: str, status_url: str = ""
	) -> PlacedCall:
		"""Start a call and return the provider's id for it."""

	@abstractmethod
	def read_webhook(self, payload: dict, url: str = "", headers: dict | None = None) -> list[CallEvent]:
		"""Turn a provider webhook into call events."""

	@abstractmethod
	def fetch_recording(self, recording_url: str) -> Recording:
		"""Download a recording."""
