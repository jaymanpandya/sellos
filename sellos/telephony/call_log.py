"""The Call Log (SOS-P2-05): one log per call, with its cost in rupees.

place_logged_call routes a call (SOS-P2-03), records the consent check (SOS-P2-04), places the call
through the provider (SOS-P2-02) and writes the Call Log. The log links to the lead, to the Consent
Check and to the live Consent Record when one exists. It holds no consent status: the screens read it
from the Consent Check. Consent never blocks here: a refusal can only come from the one consent
function, and only when the company setting "Consent enforcement" is On.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import now_datetime

from sellos.crm import consent
from sellos.telephony import router, settings
from sellos.telephony.base import ProviderError
from sellos.telephony.provider import get_provider

DOCTYPE = "Call Log"
MODES = ("Manual", "AI")
BILLING_PULSE = 60  # seconds: a call is billed by the started minute
RUPEE_PLACES = Decimal("0.0001")
_PER_RUPEE = {"rupees": Decimal(1), "paise": Decimal(100)}


def to_rupees(amount, unit="rupees") -> Decimal:
	"""A provider's cost as rupees, to four places. The unit is "rupees" or "paise"."""
	if unit not in _PER_RUPEE:
		raise ValueError(f"Unknown cost unit {unit!r}. Use rupees or paise.")
	value = Decimal(str(amount if amount not in (None, "") else 0))
	if value < 0:
		raise ValueError("A cost is never negative.")
	return (value / _PER_RUPEE[unit]).quantize(RUPEE_PLACES, rounding=ROUND_HALF_UP)


def billed_seconds(duration, pulse=BILLING_PULSE) -> int:
	"""Seconds billed for a call of `duration` seconds: rounded up to whole pulses, none for 0."""
	duration = max(int(duration or 0), 0)
	return int(math.ceil(duration / pulse) * pulse)


def _lead_number(lead) -> str:
	client = frappe.db.get_value("Lead", lead, "client")
	number = frappe.db.get_value("Client", client, "phone") if client else ""
	if not number:
		raise ProviderError(_("This lead has no phone number to call."))
	return number


def place_logged_call(lead, purpose, mode="Manual", answer_url="", status_url=""):
	"""Place a call to the lead and log it. Returns {"check": ContactCheck, "log": name or None}.

	Every attempt writes a Consent Check. A call that is not placed because enforcement is On and the
	lead is not Consented has no log, because there is no call. A provider or routing failure raises
	ProviderError and writes no log."""
	if mode not in MODES:
		frappe.throw(_("The mode must be Manual or AI."))
	if not frappe.db.exists("Lead", lead):
		frappe.throw(_("Lead {0} was not found.").format(lead), frappe.DoesNotExistError)
	number = _lead_number(lead)
	route = router.route_call(number, purpose)
	check = consent.check_contact(lead, "Call", route.purpose)
	if check.refused:
		return {"check": check, "log": None}
	auth_id, auth_token = settings._keys()
	provider = get_provider(auth_id, auth_token)
	placed = provider.place_call(route.from_number, route.to_number, answer_url, status_url)
	log = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"lead": lead,
			"provider": provider.name,
			"call_id": placed.call_id,
			"mode": mode,
			"purpose": route.purpose,
			"state": placed.state,
			"started_on": now_datetime(),
			"consent_check": check.check,
			"consent_record": consent.live_record(lead),
		}
	).insert(ignore_permissions=True)
	consent.link_check(check.check, DOCTYPE, log.name)
	return {"check": check, "log": log.name}


def apply_event(event, cost=None, cost_unit="rupees", hangup_cause=None) -> str | None:
	"""Update the log of the call an event belongs to. Returns the log name, or None for an unknown call."""
	name = frappe.db.get_value(DOCTYPE, {"call_id": event.call_id})
	if not name:
		return None
	values = {"state": event.state}
	if event.duration:
		values["duration"] = int(event.duration)
		values["billed_duration"] = billed_seconds(event.duration)
	if event.recording_url:
		values["recording_link"] = event.recording_url
	if hangup_cause is not None:
		values["hangup_cause"] = hangup_cause
	if cost is not None:
		values["cost_rupees"] = float(to_rupees(cost, cost_unit))
	frappe.db.set_value(DOCTYPE, name, values)
	return name
