"""Follow ups and reminders (SOS-P1-22).

A follow up is a Lead Task: the lead, the agent, a date and time (`due_at`, or only a day in `due_date`
for an older task) and Open or Done. This module holds the rules the lead list, the lead screen and the
reminders share, so each reads one answer:

* `due_state` says whether an open follow up is due (within 15 minutes, or today for one with only a
  day) or overdue (its time, or its day, has passed). It takes the clock as an argument, so a test fixes it.
  The reminders (`sellos.crm.notifications.notify_follow_ups`, SOS-P1-23) use it too.
* `annotate` puts each lead's next open follow up and its untouched flag on the lead rows.
* `complete` marks a follow up done and asks for the call outcome or a note.
* A lead in an Open stage with no open follow up is untouched once it has gone `untouched_days` days
  (set by the Company Admin, 3 unless changed) since it was made or since its last follow up was done.

Consent never blocks: nothing here reads a lead's consent status.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, get_datetime, getdate, now_datetime

from sellos.crm import call_outcomes, lead_labels, pipeline

SETTINGS = "SellOS Settings"
DEFAULT_UNTOUCHED_DAYS = 3
MAX_UNTOUCHED_DAYS = 365
# A follow up is "due" from this many minutes before its time.
DUE_WINDOW_MINUTES = 15
DUE = "due"
OVERDUE = "overdue"
FOLLOW_UP_FILTERS = ("overdue", "open", "none", "untouched")
SORTS = ("next_follow_up",)


def due_moment(due_at, due_date):
	"""When an open follow up falls: its time, or the start of its day when it has only a day."""
	return get_datetime(due_at) if due_at else get_datetime(due_date)


def due_state(due_at, due_date, now=None):
	"""'overdue', 'due' or None for an open follow up.

	One with a time is due from 15 minutes before it and overdue once the time has passed. One with only
	a day is due on that day and overdue after it."""
	now = get_datetime(now) if now else now_datetime()
	if due_at:
		due = get_datetime(due_at)
		if due < now:
			return OVERDUE
		return DUE if due <= add_to_date(now, minutes=DUE_WINDOW_MINUTES) else None
	day, today = getdate(due_date), getdate(now)
	return OVERDUE if day < today else DUE if day == today else None


# --- the company's setting --------------------------------------------------------------------------


def untouched_days() -> int:
	"""Days without an open follow up after which a lead in an Open stage is untouched."""
	days = cint(frappe.db.get_single_value(SETTINGS, "untouched_days"))
	return days if days > 0 else DEFAULT_UNTOUCHED_DAYS


def set_untouched_days(days) -> int:
	"""Save the Company Admin's number of days (1 to 365) and return it."""
	days = cint(days)
	if not 1 <= days <= MAX_UNTOUCHED_DAYS:
		frappe.throw(_("Enter a number of days from 1 to {0}.").format(MAX_UNTOUCHED_DAYS))
	frappe.db.set_single_value(SETTINGS, "untouched_days", days)
	return days


# --- what the lead rows carry ----------------------------------------------------------------------


def annotate(leads, now=None, days=None) -> None:
	"""Add to each lead row (a dict with name, stage, archived and creation):

	next_follow_up (its time, or its day), next_follow_up_name, next_follow_up_title,
	next_follow_up_has_time, follow_up_state (overdue, due or ""), open_follow_ups, and
	follow_up_untouched (an Open stage, no open follow up, and `days` gone since it was made or its last
	follow up was done)."""
	now = get_datetime(now) if now else now_datetime()
	days = cint(days) or untouched_days()
	names = [lead.name for lead in leads]
	open_by_lead, last_done = {}, {}
	if names:
		tasks = frappe.get_all(
			"Lead Task",
			filters={"lead": ["in", names], "archived": 0},
			fields=["name", "lead", "title", "status", "due_date", "due_at", "completed_on", "modified"],
			limit_page_length=0,
		)
		for task in tasks:
			if task.status == "Open":
				open_by_lead.setdefault(task.lead, []).append(task)
			else:
				finished = get_datetime(task.completed_on or task.modified)
				if finished > last_done.get(task.lead, finished.min):
					last_done[task.lead] = finished
	types = {stage["name"]: stage["stage_type"] for stage in pipeline.list_stages()}
	cutoff = add_days(now, -days)
	for lead in leads:
		open_tasks = sorted(
			open_by_lead.get(lead.name, []),
			key=lambda t: (due_moment(t.due_at, t.due_date), t.name),
		)
		lead["open_follow_ups"] = len(open_tasks)
		first = open_tasks[0] if open_tasks else None
		lead["next_follow_up"] = str(first.due_at or first.due_date) if first else None
		lead["next_follow_up_name"] = first.name if first else None
		lead["next_follow_up_title"] = first.title if first else None
		lead["next_follow_up_has_time"] = bool(first and first.due_at)
		lead["follow_up_state"] = (due_state(first.due_at, first.due_date, now) or "") if first else ""
		# The earliest follow up is the first to fall, so it is overdue when any of them is.
		lead["follow_up_untouched"] = bool(
			not open_tasks
			and not cint(lead.get("archived"))
			and types.get(lead.get("stage")) == "Open"
			and max(get_datetime(lead.creation), last_done.get(lead.name, get_datetime(lead.creation)))
			< cutoff
		)


def matches_filter(lead, follow_up) -> bool:
	"""Whether an annotated lead row satisfies the follow up filter."""
	if follow_up == "overdue":
		return lead["follow_up_state"] == OVERDUE
	if follow_up == "open":
		return lead["open_follow_ups"] > 0
	if follow_up == "none":
		return lead["open_follow_ups"] == 0
	return bool(lead["follow_up_untouched"])


def check_filter(follow_up, sort) -> None:
	if follow_up and follow_up not in FOLLOW_UP_FILTERS:
		frappe.throw(_("Choose one of: {0}.").format(", ".join(FOLLOW_UP_FILTERS)))
	if sort and sort not in SORTS:
		frappe.throw(_("Choose one of: {0}.").format(", ".join(SORTS)))


def sort_by_next_follow_up(leads) -> list:
	"""The leads with a follow up first, the soonest first (so overdue ones lead), then the rest in the
	order they came."""
	with_one = [lead for lead in leads if lead["next_follow_up"]]
	without = [lead for lead in leads if not lead["next_follow_up"]]
	with_one.sort(key=lambda lead: get_datetime(lead["next_follow_up"]))
	return with_one + without


# --- a person's follow ups ---------------------------------------------------------------------------


def list_follow_ups(user=None, status="Open", now=None, everyone=False) -> list[dict]:
	"""The follow ups the signed in user may see, soonest first. By default only those assigned to them.
	Each says the lead's name, its client and whether it is overdue or due."""
	user = user or frappe.session.user
	if status not in ("Open", "Done"):
		frappe.throw(_("Status must be Open or Done."))
	filters = {"archived": 0, "status": status}
	if not everyone:
		filters["assigned_to"] = user
	rows = frappe.get_list(
		"Lead Task",
		filters=filters,
		fields=["name", "lead", "title", "status", "due_date", "due_at", "assigned_to", "notes"],
		limit_page_length=0,
	)
	leads = {}
	for lead in {row.lead for row in rows}:
		leads[lead] = frappe.db.get_value("Lead", lead, ["lead_title", "client"], as_dict=True)
	now = get_datetime(now) if now else now_datetime()
	for row in rows:
		row["lead_title"] = (leads.get(row.lead) or {}).get("lead_title")
		row["due"] = str(row.due_at or row.due_date)
		row["state"] = (due_state(row.due_at, row.due_date, now) or "") if status == "Open" else ""
	lead_labels.add(rows)
	rows.sort(key=lambda row: (due_moment(row.due_at, row.due_date), row.name))
	return rows


# --- marking one done --------------------------------------------------------------------------------


def complete(
	name, outcome=None, notes=None, duration_seconds=None, follow_up_at=None, stage=None, lost_reason=None
) -> dict:
	"""Mark an open follow up done. It asks for the call outcome (SOS-P1-21) or a note, and one of the two
	is required: the outcome logs a call on the lead (with the next follow up its outcome needs), and a note
	alone is kept as a Note activity. The caller has checked the user may write the lead.
	Returns {"task", "activity", "follow_up", "suggested_stage", "stage", "moved", "warning"}."""
	task = frappe.get_doc("Lead Task", name)
	task.check_permission("write")
	if task.archived:
		frappe.throw(_("An archived follow up cannot be completed."))
	if task.status == "Done":
		frappe.throw(_("This follow up is already done."))
	outcome = (outcome or "").strip()
	notes = (notes or "").strip()
	if not outcome and not notes:
		frappe.throw(_("Choose the call outcome or write a note."), frappe.MandatoryError)
	if outcome:
		result = call_outcomes.log_call(
			task.lead, outcome, notes or None, duration_seconds, follow_up_at, stage, lost_reason
		)
	else:
		activity = frappe.get_doc(
			{
				"doctype": "Lead Activity",
				"lead": task.lead,
				"activity_type": "Note",
				"activity_date": now_datetime(),
				"notes": notes,
			}
		)
		activity.check_permission("create")
		activity.flags.ignore_permissions = True
		activity.insert()
		result = {
			"activity": activity.name,
			"follow_up": None,
			"suggested_stage": None,
			"stage": frappe.db.get_value("Lead", task.lead, "stage"),
			"moved": False,
			"warning": None,
		}
	task.status = "Done"
	task.flags.ignore_permissions = True  # checked above
	task.save()
	return {"task": task.name, **result}
