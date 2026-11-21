"""A missed call to the 022 number (SOS-P2-08).

The provider reports a call made to our number as an event with the direction `inbound`. The call is
never answered: the number is for service and transactional calls, and a missed call is the way a bought
lead says "call me". A call that ends with no talk time (no answer, busy, cancelled, or completed in zero
seconds) is a missed call. It goes to `sellos.crm.intake.take`, which matches the caller or makes a new
lead on the New stage, records an inquiry Consent Record for 7 days and logs an activity. No stage moves.

This runs inside the provider webhook (SOS-P2-06), so the signature, the replay key and the rate limit
have been checked. A second event of the same call (the provider may send two) is remembered by its call
ID and changes nothing. Whether the provider bills a rejected call is checked on a real call (SOS-P2-13).
"""

import frappe
from frappe.utils import now

from sellos.access.webhooks import remember_event
from sellos.crm import intake
from sellos.crm.duplicates import normalise_phone
from sellos.crm.lead_sources import MISSED_CALL
from sellos.telephony.base import CallEvent

INBOUND = "inbound"
ENDED = ("completed", "no-answer", "busy", "cancelled", "failed")


def our_number() -> str:
	"""The 022 number as the provider reports it, or an empty string when none is saved."""
	return normalise_phone(frappe.db.get_single_value("Telephony Settings", "phone_number") or "")


def is_missed_call(event: CallEvent) -> bool:
	"""True for an inbound call to our number that has ended with no talk time."""
	number = our_number()
	return bool(
		number
		and event.direction == INBOUND
		and normalise_phone(event.to_number) == number
		and event.state in ENDED
		and not event.duration
		and normalise_phone(event.from_number)
	)


def handle_missed_call(event: CallEvent) -> dict | None:
	"""Record the missed call, once per call. Returns the intake result, or None when it is not one."""
	if not is_missed_call(event) or not remember_event("plivo-missed-call", event.call_id):
		return None
	return intake.take(
		phone=event.from_number,
		source=MISSED_CALL,
		kind="missed-call",
		reference=frappe.scrub(event.call_id)[:40] or frappe.generate_hash(length=8),
		evidence={"event": event.raw, "call_id": event.call_id, "received_on": now()},
		notes="Missed call to the 022 number. The caller asked to be called back.",
		activity_type=intake.CALL,
	)
