"""Calling hours (SOS-P2-10): a company setting, in India time.

The setting lives in Telephony Settings: a switch, a start time, an end time and the days. With the
switch off (the default) a call may be placed at any time. With it on, a call is allowed from the start
time up to but not including the end time, on the chosen days. A call outside them is refused with the
hours in the message.

This is a calling hours rule, not a consent check. Consent never blocks (Jayman, 10 November 2026): the
only consent refusal is the one function in sellos.crm.consent, and only when Consent enforcement is On.
The check runs in the dial path (the call router, SOS-P2-03) before a call is placed.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import cint, get_time

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.telephony.base import ProviderError

DOCTYPE = "Telephony Settings"
IST = ZoneInfo("Asia/Kolkata")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DEFAULT_START = time(9, 0)
DEFAULT_END = time(21, 0)
DEFAULT_DAYS = DAYS[:6]


def now_ist() -> datetime:
	return datetime.now(IST)


def _to_ist(value) -> datetime:
	if value is None:
		return now_ist()
	return value.replace(tzinfo=IST) if value.tzinfo is None else value.astimezone(IST)


def _clock(value, default) -> time:
	try:
		return get_time(value) if value else default
	except Exception:
		return default


def _days(value) -> tuple[str, ...]:
	chosen = [d.strip().title() for d in str(value or "").split(",") if d.strip()]
	days = tuple(d for d in DAYS if d in chosen)
	return days or DEFAULT_DAYS


def get_rule() -> dict:
	"""The company's calling hours: enabled, start and end as HH:MM, and the days."""
	row = frappe.db.get_singles_dict(DOCTYPE) or {}
	start = _clock(row.get("calling_hours_start"), DEFAULT_START)
	end = _clock(row.get("calling_hours_end"), DEFAULT_END)
	return {
		"enabled": bool(cint(row.get("calling_hours_enabled"))),
		"start": start.strftime("%H:%M"),
		"end": end.strftime("%H:%M"),
		"days": list(_days(row.get("calling_days"))),
	}


def _clock_text(value: time) -> str:
	hour = value.hour % 12 or 12
	return f"{hour}:{value.minute:02d} {'am' if value.hour < 12 else 'pm'}"


def _days_text(days) -> str:
	idx = [DAYS.index(d) for d in days]
	if len(idx) == 7:
		return _("every day")
	if len(idx) > 2 and idx == list(range(idx[0], idx[0] + len(idx))):
		return _("{0} to {1}").format(_(DAY_NAMES[idx[0]]), _(DAY_NAMES[idx[-1]]))
	return ", ".join(_(DAY_NAMES[i]) for i in idx)


def hours_text(rule=None) -> str:
	rule = rule or get_rule()
	return _("{0} to {1}, {2}, India time").format(
		_clock_text(get_time(rule["start"])), _clock_text(get_time(rule["end"])), _days_text(rule["days"])
	)


def is_within(now=None, rule=None) -> bool:
	"""True when `now` (India time unless it carries a zone) is inside the calling hours."""
	rule = rule or get_rule()
	if not rule["enabled"]:
		return True
	moment = _to_ist(now)
	if DAYS[moment.weekday()] not in rule["days"]:
		return False
	return get_time(rule["start"]) <= moment.time().replace(tzinfo=None) < get_time(rule["end"])


def check_calling_hours(now=None) -> None:
	"""Raise ProviderError, with the hours in the message, when a call now is outside the calling hours."""
	rule = get_rule()
	if not is_within(now, rule):
		raise ProviderError(
			_("Calls can only be placed {0}. Try again within these hours.").format(hours_text(rule))
		)


def save_rule(enabled, start, end, days) -> dict:
	"""Validate and save the calling hours."""
	start_t, end_t = _clock(start, None), _clock(end, None)
	if not start_t or not end_t:
		frappe.throw(_("Enter the start and the end of the calling hours, for example 09:00 and 21:00."))
	if start_t >= end_t:
		frappe.throw(_("The calling hours must end after they start."))
	if isinstance(days, str):
		days = [d for d in days.replace(";", ",").split(",")]
	chosen = [str(d).strip().title()[:3] for d in (days or []) if str(d).strip()]
	if not chosen or any(d not in DAYS for d in chosen):
		frappe.throw(_("Choose at least one calling day from Monday to Sunday."))
	doc = frappe.get_doc(DOCTYPE)
	doc.calling_hours_enabled = 1 if cint(enabled) else 0
	doc.calling_hours_start = start_t.strftime("%H:%M:%S")
	doc.calling_hours_end = end_t.strftime("%H:%M:%S")
	doc.calling_days = ",".join(d for d in DAYS if d in chosen)
	doc.flags.ignore_permissions = True
	doc.save()
	return state()


def state() -> dict:
	rule = get_rule()
	return {**rule, "text": hours_text(rule) if rule["enabled"] else "", "all_days": list(DAYS)}


@sellos_api(COMPANY_ADMIN)
def get_calling_hours():
	"""The company's calling hours (SOS-P2-10)."""
	return state()


@sellos_api(COMPANY_ADMIN)
def save_calling_hours(enabled=1, start="09:00", end="21:00", days="Mon,Tue,Wed,Thu,Fri,Sat"):
	"""Save the calling hours, in India time (SOS-P2-10). A call outside them is refused."""
	return save_rule(enabled, start, end, days)
