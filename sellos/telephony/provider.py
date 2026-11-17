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

from abc import ABC, abstractmethod

import frappe
from frappe import _

DEFAULT_PROVIDER = "plivo"


class ProviderError(Exception):
	"""A provider failure with a message that is safe to show to a person (it never holds a key)."""


class TelephonyProvider(ABC):
	name = ""

	def __init__(self, auth_id: str, auth_token: str):
		self.auth_id = auth_id
		self.auth_token = auth_token

	@abstractmethod
	def test_connection(self) -> str:
		"""Check the keys with the provider. Return a short message on success, raise ProviderError
		with a clear message otherwise."""


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


# provider name -> class. SOS-P2-02 adds "plivo".
PROVIDERS: dict[str, type[TelephonyProvider]] = {FakeProvider.name: FakeProvider}


def get_provider(auth_id: str, auth_token: str) -> TelephonyProvider:
	name = frappe.db.get_single_value("Telephony Settings", "provider") or DEFAULT_PROVIDER
	provider = PROVIDERS.get(name)
	if provider is None or (name == FakeProvider.name and not frappe.conf.get("allow_tests")):
		raise ProviderError(_("The calling provider is not available on this site yet."))
	return provider(auth_id, auth_token)
