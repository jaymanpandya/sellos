"""In-app notifications (SOS-P1-23).

Five events tell a user what needs them: a lead assigned to them, a lead reassigned away from them, a
follow up due in the next 15 minutes, a follow up that became overdue, and a site visit tomorrow. Each
becomes one App Notification for one recipient, made by `notify`, which is the only function that
writes one.

* A notification belongs to its recipient. `unread_for`, `mark_read` and `mark_all_read` act on the
  signed in user's notifications and nobody else's.
* A user never learns of a record they may not see. `notify` makes nothing for a lead the recipient
  cannot read, and `unread_for` leaves out one the recipient can no longer read. A lead reassigned
  away is the one event whose recipient has just lost the lead, so its notification then carries no
  lead and no client name, only the fact.
* A person is not told about their own action: assigning a lead to yourself notifies nobody.
* The scheduler functions are safe to run again: a dedupe key stops the same thing being told twice.
* Consent never blocks: nothing here looks at consent.

Email copies (SOS-P0-13, SOS-P1-26): `send_copies` is the one place to add them. It runs once for each
notification made, with the saved App Notification, and sends nothing today.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, get_datetime, get_fullname, getdate, now_datetime

from sellos.crm import follow_ups

DOCTYPE = "App Notification"
LEAD_ASSIGNED = "Lead assigned"
LEAD_REASSIGNED_AWAY = "Lead reassigned away"
FOLLOW_UP_DUE = "Follow up due"
FOLLOW_UP_OVERDUE = "Follow up overdue"
SITE_VISIT_TOMORROW = "Site visit tomorrow"
RESPONSE_MISSED = "Response time missed"  # SOS-P7-13
WHATSAPP_HANDOFF = "WhatsApp handoff"  # SOS-P6-11
# A follow up is "due" from this many minutes before its time.
DUE_WINDOW_MINUTES = follow_ups.DUE_WINDOW_MINUTES
# The bell lists this many, newest first. The unread count is of all of them.
LIST_LIMIT = 50


def can_see_lead(user, lead) -> bool:
	"""True when this user may read the lead: the one test every notification passes before it is made
	and again before it is shown."""
	if not user or not lead or not frappe.db.get_value("User", user, "enabled"):
		return False
	if not frappe.db.exists("Lead", lead):
		return False
	return bool(frappe.has_permission("Lead", "read", doc=lead, user=user))


def send_copies(notification) -> None:
	"""The one place to add the email copy of a notification (SOS-P0-13, SOS-P1-26). `notification` is the
	saved App Notification. Nothing is sent until outgoing email exists."""


def notify(recipient, event, title, message=None, lead=None, dedupe_key=None):
	"""Make one notification for one user and return its name, or None when nothing was made: the lead
	is not one the recipient may see, or the dedupe key was already used."""
	if lead and not can_see_lead(recipient, lead):
		return None
	if dedupe_key and frappe.db.exists(DOCTYPE, {"dedupe_key": dedupe_key}):
		return None
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"recipient": recipient,
			"event": event,
			"title": title,
			"message": message,
			"lead": lead,
			"dedupe_key": dedupe_key,
		}
	).insert(ignore_permissions=True)
	send_copies(doc)
	return doc.name


# --- events made by a save ---------------------------------------------------------------------------


def notify_lead_assignment(lead) -> None:
	"""Run after a lead is saved: tell the new assignee, and the one it was taken from. Nobody is told
	of their own change."""
	previous = lead.get_doc_before_save()
	old = previous.assigned_to if previous else None
	new = lead.assigned_to
	if old == new:
		return
	actor = frappe.session.user
	if new and new != actor:
		notify(
			new,
			LEAD_ASSIGNED,
			_("Lead assigned to you"),
			_("{0} was assigned to you.").format(lead.lead_title),
			lead=lead.name,
		)
	if old and old != actor:
		if can_see_lead(old, lead.name):
			notify(
				old,
				LEAD_REASSIGNED_AWAY,
				_("Lead reassigned"),
				_("{0} was reassigned to {1}.").format(
					lead.lead_title, get_fullname(new) if new else _("no one")
				),
				lead=lead.name,
			)
		else:  # the lead is no longer theirs to see, so the notice says nothing about it
			notify(old, LEAD_REASSIGNED_AWAY, _("A lead was reassigned away from you"))


# --- events made by the scheduler ----------------------------------------------------------------------


def _lead_row(lead, cache):
	if lead not in cache:
		cache[lead] = frappe.db.get_value(
			"Lead", lead, ["lead_title", "assigned_to", "archived"], as_dict=True
		)
	return cache[lead]


def notify_follow_ups(now=None) -> int:
	"""Tell each agent of an open follow up that is due within 15 minutes, and of one that is overdue.
	A task with a time (SOS-P1-21) is due at that time. One with only a date is due on that day and
	overdue after it. Each event is told once per task and due time. Returns how many were made."""
	now = get_datetime(now) if now else now_datetime()
	soon = add_to_date(now, minutes=DUE_WINDOW_MINUTES)
	tasks = frappe.get_all(
		"Lead Task",
		filters={"status": "Open", "archived": 0},
		or_filters=[["due_at", "<=", soon], ["due_date", "<=", getdate(now)]],
		fields=["name", "lead", "title", "due_date", "due_at", "assigned_to"],
		limit_page_length=0,
	)
	leads, made = {}, 0
	for task in tasks:
		state = follow_ups.due_state(task.due_at, task.due_date, now)
		event = FOLLOW_UP_OVERDUE if state == follow_ups.OVERDUE else FOLLOW_UP_DUE if state else None
		if task.due_at:
			when = get_datetime(task.due_at).strftime("%d %b, %I:%M %p")
		else:
			when = getdate(task.due_date).strftime("%d %b")
		lead = _lead_row(task.lead, leads)
		recipient = task.assigned_to or (lead and lead.assigned_to)
		if not event or not recipient or not lead or lead.archived:
			continue
		title = _("Follow up overdue") if event == FOLLOW_UP_OVERDUE else _("Follow up due")
		message = _("{0} for {1}, due {2}.").format(task.title, lead.lead_title, when)
		key = f"{event}:{task.name}:{task.due_at or task.due_date}"
		made += bool(notify(recipient, event, title, message, lead=task.lead, dedupe_key=key))
	return made


def notify_site_visits(now=None) -> int:
	"""Tell the agent of a scheduled site visit that it is tomorrow. Returns how many were made."""
	now = get_datetime(now) if now else now_datetime()
	start = get_datetime(add_days(getdate(now), 1))
	visits = frappe.get_all(
		"Site Visit",
		filters=[
			["status", "=", "Scheduled"],
			["archived", "=", 0],
			["visit_datetime", ">=", start],
			["visit_datetime", "<", add_days(start, 1)],
		],
		fields=["name", "lead", "project_name", "visit_datetime", "agent"],
		limit_page_length=0,
	)
	leads, made = {}, 0
	for visit in visits:
		lead = _lead_row(visit.lead, leads)
		recipient = visit.agent or (lead and lead.assigned_to)  # the visit's agent (SOS-P1-25)
		if not lead or lead.archived or not recipient:
			continue
		at = get_datetime(visit.visit_datetime)
		message = _("Site visit for {0} at {1} tomorrow, {2}.").format(
			lead.lead_title, visit.project_name or _("the project"), at.strftime("%I:%M %p")
		)
		key = f"{SITE_VISIT_TOMORROW}:{visit.name}:{visit.visit_datetime}"
		made += bool(
			notify(recipient, SITE_VISIT_TOMORROW, _("Site visit tomorrow"), message, visit.lead, key)
		)
	return made


# --- what the bell reads -------------------------------------------------------------------------------


def unread_for(user=None, limit=LIST_LIMIT) -> dict:
	"""The user's unread notifications, newest first, and how many there are. One about a lead the user
	can no longer read is left out and not counted."""
	user = user or frappe.session.user
	rows = frappe.get_all(
		DOCTYPE,
		filters={"recipient": user, "is_read": 0},
		fields=["name", "event", "title", "message", "lead", "creation"],
		order_by="creation desc, name desc",
		limit_page_length=0,
	)
	seen = {}
	items = []
	for row in rows:
		if row.lead:
			if row.lead not in seen:
				seen[row.lead] = can_see_lead(user, row.lead)
			if not seen[row.lead]:
				continue
		items.append(row)
	return {"unread": len(items), "items": items[: cint(limit) or LIST_LIMIT]}


def _own(name, user):
	row = frappe.db.get_value(DOCTYPE, name, ["recipient"], as_dict=True)
	if not row or row.recipient != user:  # another user's reads the same as a missing one
		frappe.throw(_("Notification not found."), frappe.DoesNotExistError)


def mark_read(name, user=None) -> dict:
	"""Mark one of the user's own notifications read, and return what is still unread."""
	user = user or frappe.session.user
	_own(name, user)
	frappe.db.set_value(DOCTYPE, name, {"is_read": 1, "read_on": now_datetime()})
	return {"unread": unread_for(user, limit=1)["unread"]}


def mark_all_read(user=None) -> dict:
	"""Mark every unread notification of the user read."""
	user = user or frappe.session.user
	frappe.db.set_value(DOCTYPE, {"recipient": user, "is_read": 0}, {"is_read": 1, "read_on": now_datetime()})
	return {"unread": 0}
