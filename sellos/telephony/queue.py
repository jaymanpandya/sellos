"""The caller queue (SOS-P2-09).

The leads a caller may call, ordered by urgency so no consent window is wasted:

1. Consented leads whose consent lapses, soonest expiry first, each with the time left.
2. Consented leads whose consent never lapses (a Consent record has no expiry).
3. Everyone else: Unknown, then Registered DND, then Opted out.

Within a group the order is the lead's creation, then its name, so the queue never reshuffles.

Consent never blocks (Jayman, 10 November 2026). Every lead the caller may see is in the queue, whatever
its consent status, and each carries its warning: amber for Unknown and Registered DND, red for Opted
out. Nothing here drops or refuses a lead. Enforcement lives only in `sellos.crm.consent.check_contact`.

Who may see a lead is Frappe's own permission query on Lead (an Agent their own, a Sales Manager their
team's, a Company Admin everyone's), so the queue never widens it.
"""

import frappe
from frappe.utils import get_datetime, now_datetime

from sellos.crm import consent, lead_labels

# The order of the leads that are not Consented.
_REST_ORDER = {consent.UNKNOWN: 0, consent.REGISTERED_DND: 1, consent.OPTED_OUT: 2}


def time_left_text(seconds) -> str:
	"""A short, human time left: "2 days 3 hours", "5 hours 10 minutes", "12 minutes", "Expired"."""
	seconds = int(seconds)
	if seconds <= 0:
		return "Expired"
	days, rest = divmod(seconds, 86400)
	hours, rest = divmod(rest, 3600)
	minutes = rest // 60
	parts = []
	for count, unit in ((days, "day"), (hours, "hour"), (minutes, "minute")):
		if count:
			parts.append(f"{count} {unit}{'' if count == 1 else 's'}")
	return " ".join(parts[:2]) or "Less than a minute"


def _live_windows(leads, on) -> dict:
	"""For each lead with a live Consent Record: the moment its consent lapses, or None when a live record
	never lapses. The window lasts as long as the longest live record."""
	if not leads:
		return {}
	rows = frappe.db.sql(
		"""select lead, expires_on from `tabConsent Record`
		where lead in %(leads)s and archived = 0 and recorded_on <= %(on)s
		and (expires_on is null or expires_on > %(on)s)""",
		{"leads": tuple(leads), "on": on},
		as_dict=True,
	)
	windows = {}
	for row in rows:
		expires = get_datetime(row.expires_on) if row.expires_on else None
		if row.lead not in windows:
			windows[row.lead] = expires
		elif windows[row.lead] is not None:
			windows[row.lead] = None if expires is None else max(windows[row.lead], expires)
	return windows


def caller_queue(now=None) -> list[dict]:
	"""The queue for the signed in user, in order. Each row has the lead, its client, stage and agent, the
	consent status with its warning level and message, `expires_on` and `time_left` (seconds and text, only
	for a Consented lead that lapses), and `position` (1 for the first to call)."""
	on = get_datetime(now) if now else now_datetime()
	leads = frappe.get_list(
		"Lead",
		filters={"archived": 0},
		fields=[
			"name",
			"lead_title",
			"client",
			"stage",
			"assigned_to",
			"creation",
			"opted_out_on",
			"dnd_registered",
			"pipeline",
		],
		order_by="creation asc, name asc",
		limit_page_length=0,
	)
	windows = _live_windows([lead.name for lead in leads], on)
	rows = []
	for lead in leads:
		# The same order of precedence as consent.compute_status, read in bulk.
		if lead.opted_out_on:
			status = consent.OPTED_OUT
		elif lead.dnd_registered:
			status = consent.REGISTERED_DND
		elif lead.name in windows:
			status = consent.CONSENTED
		else:
			status = consent.UNKNOWN
		level, message = consent.WARNINGS[status]
		expires = windows.get(lead.name) if status == consent.CONSENTED else None
		left = int((expires - on).total_seconds()) if expires else None
		rows.append(
			{
				"lead": lead.name,
				"lead_title": lead.lead_title,
				"client": lead.client,
				"stage": lead.stage,
				"pipeline": lead.pipeline,
				"assigned_to": lead.assigned_to,
				"consent_status": status,
				"consent_warning": level,
				"consent_message": message,
				"expires_on": str(expires) if expires else None,
				"seconds_left": left,
				"time_left": time_left_text(left) if left is not None else None,
				"_creation": lead.creation,
			}
		)

	def urgency(row):
		if row["consent_status"] == consent.CONSENTED:
			lapses = row["seconds_left"] is not None
			return (0 if lapses else 1, row["seconds_left"] or 0)
		return (2 + _REST_ORDER[row["consent_status"]], 0)

	rows.sort(key=lambda row: (urgency(row), row["_creation"], row["lead"]))
	for position, row in enumerate(rows, start=1):
		row["position"] = position
		del row["_creation"]
	lead_labels.add(rows)
	return rows
