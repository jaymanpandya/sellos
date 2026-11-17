"""The call router (SOS-P2-03): which account and which number a call goes through.

International calling is dropped (Jayman, 10 November 2026), so there is one account, the India
account of Telephony Settings, and one series, the 022 landline number. A +91 mobile number is routed
through them. Every other country code is refused with a clear message. A 140 series route is parked
and does not exist here.

The 022 number is for service and transactional calls. Each call records its purpose. A promotional
purpose is not refused: the route carries a warning, which the call log shows (SOS-P2-05). Consent
never blocks here: the router does not look at consent.
"""

import re
from dataclasses import dataclass

import frappe
from frappe import _

from sellos.telephony.base import ProviderError, TelephonyProvider

ACCOUNT_INDIA = "india"
SERIES_022 = "022"

SERVICE = "Service"
TRANSACTIONAL = "Transactional"
PROMOTIONAL = "Promotional"
PURPOSES = (SERVICE, TRANSACTIONAL, PROMOTIONAL)

# An Indian mobile number in E.164: +91, then ten digits that start with 6, 7, 8 or 9.
_IN_MOBILE = re.compile(r"^\+91[6-9]\d{9}$")


@dataclass(frozen=True)
class Route:
	"""Where one call goes: the account, the series, the number it is placed from and its purpose.

	warning is empty unless the purpose is not one the 022 number is meant for."""

	account: str
	series: str
	from_number: str
	to_number: str
	purpose: str
	warning: str = ""


def _compact(number: str) -> str:
	return re.sub(r"[\s\-()]", "", number or "")


def route_call(to_number: str, purpose: str, from_number: str | None = None) -> Route:
	"""Route a call to `to_number` for `purpose`. Raises ProviderError with a message safe to show.

	from_number is the 022 number; it defaults to the one saved in Telephony Settings."""
	purpose = (purpose or "").strip().title()
	if purpose not in PURPOSES:
		raise ProviderError(_("Choose the purpose of the call: Service, Transactional or Promotional."))
	number = _compact(to_number)
	if not number.startswith("+"):
		raise ProviderError(_("Enter the number with its country code, for example +91."))
	if not number.startswith("+91"):
		raise ProviderError(_("Only calls to Indian numbers (+91) are supported. Other countries are not."))
	if not _IN_MOBILE.match(number):
		raise ProviderError(_("This is not a valid Indian mobile number."))
	if from_number is None:
		from_number = frappe.db.get_single_value("Telephony Settings", "phone_number") or ""
	if not from_number:
		raise ProviderError(_("The 022 number is not set. Ask your Company Admin to add it."))
	return Route(ACCOUNT_INDIA, SERIES_022, from_number, number, purpose, purpose_warning(purpose))


def place_routed_call(
	provider: TelephonyProvider,
	to_number: str,
	purpose: str,
	answer_url: str,
	status_url: str = "",
	from_number: str | None = None,
):
	"""Route the call, then place it through `provider`. Returns (Route, PlacedCall)."""
	route = route_call(to_number, purpose, from_number)
	return route, provider.place_call(route.from_number, route.to_number, answer_url, status_url)


def purpose_warning(purpose: str) -> str:
	"""The warning the call log shows for a purpose, or an empty string."""
	if (purpose or "").strip().title() == PROMOTIONAL:
		return _("The 022 number is for service and transactional calls. This call is promotional.")
	return ""


__all__ = ["PURPOSES", "Route", "place_routed_call", "purpose_warning", "route_call"]
