"""The telephony provider interface (SOS-P2-01).

One interface sits between SellOS and a calling provider, so Plivo can be replaced later. SOS-P2-01
defines it with `test_connection` only; SOS-P2-02 extends it with place call, read webhook and fetch
recording and registers the Plivo adapter. Until then the only provider that exists is the fake one,
which never leaves the process and holds no real key. The agent that builds SellOS never calls the
real provider.

Which provider runs comes from the hidden `provider` field of Telephony Settings (empty means
"plivo"). It is in the database, not in site_config, because a web server keeps site_config in memory
for a minute and would not see a change made by another process. The fake provider is chosen only
on a site that allows tests. A name with no registered provider is reported as not available, never
as a success.
"""

import frappe
from frappe import _

from sellos.telephony.base import (
	CALL_STATES,
	CallEvent,
	PlacedCall,
	ProviderError,
	Recording,
	TelephonyProvider,
)
from sellos.telephony.plivo import PlivoProvider

DEFAULT_PROVIDER = "plivo"

__all__ = ["CALL_STATES", "CallEvent", "PlacedCall", "ProviderError", "Recording", "TelephonyProvider"]


class FakeProvider(TelephonyProvider):
	"""A provider for tests and demos. The auth ID decides the answer:

	* starts with FAKEOK: the connection works,
	* starts with FAKEDOWN: the provider can not be reached,
	* anything else (or a missing key): the keys are refused.
	"""

	name = "fake"

	def test_connection(self) -> str:
		auth_id = self.auth_id or ""
		if auth_id.startswith("FAKEDOWN"):
			raise ProviderError(_("The provider could not be reached. Try again in a few minutes."))
		if not auth_id.startswith("FAKEOK") or not self.auth_token:
			raise ProviderError(_("The provider refused these keys. Check the auth ID and the auth token."))
		return _("Connected. The provider accepted the keys.")

	def _check_keys(self):
		self.test_connection()

	def place_call(
		self, from_number: str, to_number: str, answer_url: str, status_url: str = ""
	) -> PlacedCall:
		self._check_keys()
		if not from_number or not to_number:
			raise ProviderError(_("Both numbers are needed to place a call."))
		# Unique per call, as a real provider's id is: two calls to one number are two calls (SOS-P2-07).
		return PlacedCall(
			call_id=f"fake-{from_number[-6:]}-{to_number[-6:]}-{frappe.generate_hash(length=8)}"
		)

	def read_webhook(self, payload: dict, url: str = "", headers: dict | None = None) -> list[CallEvent]:
		"""The fake payload is {"call_id", "state", "duration", "from", "to", "recording_url"}."""
		state = payload.get("state")
		if not payload.get("call_id") or state not in CALL_STATES:
			raise ProviderError(_("The provider sent an event that could not be read."))
		return [
			CallEvent(
				call_id=payload["call_id"],
				state=state,
				from_number=payload.get("from", ""),
				to_number=payload.get("to", ""),
				duration=int(payload.get("duration") or 0),
				recording_url=payload.get("recording_url", ""),
				raw=dict(payload),
				direction=str(payload.get("direction") or "").lower(),
			)
		]

	def fetch_recording(self, recording_url: str) -> Recording:
		self._check_keys()
		if not recording_url:
			raise ProviderError(_("The recording was not found."))
		return Recording(content=b"fake-recording:" + recording_url.encode(), content_type="audio/mpeg")


# provider name -> class.
PROVIDERS: dict[str, type[TelephonyProvider]] = {
	FakeProvider.name: FakeProvider,
	PlivoProvider.name: PlivoProvider,
}


def get_provider(auth_id: str, auth_token: str) -> TelephonyProvider:
	name = frappe.db.get_single_value("Telephony Settings", "provider") or DEFAULT_PROVIDER
	provider = PROVIDERS.get(name)
	allow_tests = bool(frappe.conf.get("allow_tests"))
	# The fake runs only on a site that allows tests. The live Plivo never runs there, so a test can
	# not reach the real provider (SOS-P2-02); tests give PlivoProvider a recorded transport instead.
	wrong_site = (name == FakeProvider.name and not allow_tests) or (
		name == PlivoProvider.name and allow_tests
	)
	if provider is None or wrong_site:
		raise ProviderError(_("The calling provider is not available on this site yet."))
	return provider(auth_id, auth_token)
