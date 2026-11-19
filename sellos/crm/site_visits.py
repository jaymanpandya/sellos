"""Site visits: booking, the calendar, tomorrow's confirmations and marking one done (SOS-P1-25).

A site visit is a Site Visit record: the lead, the project, the date and time, the agent who takes it,
a status (Scheduled, Done or Cancelled) and a confirmation status the agent sets after the call the day
before (Not confirmed, Confirmed, Rescheduled, Cancelled). This module holds the rules the lead screen, the
calendar and the list of tomorrow's visits share:

* `book` saves a visit. A new one moves its lead to Site visit booked unless the lead is already further
  on in the pipeline. The agent is told the day before by `sellos.crm.notifications.notify_site_visits`.
* `calendar` and `tomorrows_visits` read the visits the user may see: an Agent their own, a Sales Manager
  those of their team, a Company Admin everyone's.
* `confirm` records the confirmation status. Rescheduled needs the new time. Cancelled cancels the visit.
* `complete` marks a visit Done, asks for the outcome and returns the next stage it offers. The stage is
  offered and never applied for the agent.

Consent never blocks: nothing here reads a lead's consent status.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime

from sellos.access import lead_permissions
from sellos.crm import pipeline

DOCTYPE = "Site Visit"
SCHEDULED = "Scheduled"
DONE = "Done"
CANCELLED = "Cancelled"
STATUSES = (SCHEDULED, DONE, CANCELLED)

NOT_CONFIRMED = "Not confirmed"
CONFIRMED = "Confirmed"
RESCHEDULED = "Rescheduled"
CONFIRMATIONS = (NOT_CONFIRMED, CONFIRMED, RESCHEDULED, CANCELLED)

# The outcome of a visit that took place, and the stage each one offers next. Did not come offers none.
OUTCOME_STAGES = {
	"Liked it": pipeline.NEGOTIATION,
	"Undecided": pipeline.SITE_VISIT_DONE,
	"Wants a second visit": pipeline.SITE_VISIT_DONE,
	"Not interested": pipeline.CLOSED_LOST,
	"Did not come": None,
}
OUTCOMES = tuple(OUTCOME_STAGES)
VIEWS = ("day", "week")
VISIT_FIELDS = [
	"name",
	"lead",
	"project_name",
	"visit_datetime",
	"agent",
	"status",
	"confirmation_status",
	"visit_outcome",
	"outcome_notes",
	"notes",
]


# --- the stage a booking moves the lead to -----------------------------------------------------------


def _position(stage):
	return frappe.db.get_value(pipeline.STAGE, stage, "position") if stage else None


def moves_to_booked(current) -> bool:
	"""Whether booking a visit moves a lead now on `current` to Site visit booked.

	A lead with no stage, or on an Open stage before Site visit booked (New, Consent pending, Contacted,
	Qualified), or on Nurture, moves. A lead already on Site visit booked or further on (Site visit done,
	Negotiation, Booking, Closed won, Closed lost) stays where it is. A company that removed the Site visit
	booked stage keeps every lead where it is."""
	booked = _position(pipeline.SITE_VISIT_BOOKED)
	if booked is None:
		return False
	if not current:
		return True
	if current == pipeline.NURTURE:
		return True
	position = _position(current)
	return position is not None and position < booked


# --- booking -----------------------------------------------------------------------------------------


def _agent_for(lead_doc, agent=None) -> str:
	"""The agent taking the visit: the one chosen, else the lead's agent, else the signed in user."""
	agent = agent or lead_doc.assigned_to or frappe.session.user
	if not frappe.db.get_value("User", agent, "enabled"):
		frappe.throw(_("{0} is not an active user.").format(agent))
	return agent


def book(values, name=None) -> dict:
	"""Create or change a visit with the user's own permission checked. A new visit moves its lead to Site
	visit booked unless it is further on (`moves_to_booked`). Returns the visit with "stage_moved" and
	"lead_stage"."""
	if name:
		doc = frappe.get_doc(DOCTYPE, name)
		doc.check_permission("write")
		doc.update(values)
		if "agent" in values:
			doc.agent = _agent_for(frappe.get_doc("Lead", doc.lead), values.get("agent"))
		doc.flags.ignore_permissions = True  # checked above
		doc.save()
		return {
			**doc.as_dict(),
			"stage_moved": False,
			"lead_stage": frappe.db.get_value("Lead", doc.lead, "stage"),
		}
	doc = frappe.get_doc({"doctype": DOCTYPE, **values})
	lead_doc = frappe.get_doc("Lead", doc.lead)
	doc.check_permission("create")
	doc.agent = _agent_for(lead_doc, values.get("agent"))
	doc.flags.ignore_permissions = True
	doc.insert()
	moved = False
	if moves_to_booked(lead_doc.stage):
		moved = pipeline.move_lead(doc.lead, pipeline.SITE_VISIT_BOOKED)["moved"]
	return {
		**doc.as_dict(),
		"stage_moved": moved,
		"lead_stage": frappe.db.get_value("Lead", doc.lead, "stage"),
	}


# --- who sees which visits ---------------------------------------------------------------------------


def _agent_filter(user=None):
	"""None for a user who sees every visit, else the agents whose visits the user sees."""
	user = user or frappe.session.user
	scope = lead_permissions.scope_for(frappe.get_roles(user))
	if scope == "all" or user == "Administrator":
		return None
	if scope == "team":
		return lead_permissions.visible_users(user, "team")
	return [user]


def _rows(start, end, user=None, now=None) -> list[dict]:
	"""The visits from `start` up to, not including, `end`, for the user, soonest first. The DocType's
	permission already limits them to leads the user may see."""
	filters = [
		["archived", "=", 0],
		["visit_datetime", ">=", start],
		["visit_datetime", "<", end],
	]
	agents = _agent_filter(user)
	if agents is not None:
		filters.append(["agent", "in", agents])
	rows = frappe.get_list(
		DOCTYPE,
		filters=filters,
		fields=VISIT_FIELDS,
		order_by="visit_datetime asc, name asc",
		limit_page_length=0,
	)
	titles = {}
	for lead in {row.lead for row in rows}:
		titles[lead] = frappe.db.get_value("Lead", lead, "lead_title")
	names = {}
	for agent in {row.agent for row in rows if row.agent}:
		names[agent] = frappe.db.get_value("User", agent, "full_name") or agent
	for row in rows:
		row["lead_title"] = titles.get(row.lead)
		row["agent_name"] = names.get(row.agent, "")
		row["visit_datetime"] = str(row.visit_datetime)
	return rows


def _window(view, date):
	"""The first day and the day after the last of a day or week view. A week runs Monday to Sunday."""
	if view not in VIEWS:
		frappe.throw(_("Choose one of: {0}.").format(", ".join(VIEWS)))
	day = getdate(date) if date else getdate(now_datetime())
	if view == "week":
		day = add_days(day, -day.weekday())
		return day, add_days(day, 7)
	return day, add_days(day, 1)


def calendar(view="week", date=None, user=None) -> dict:
	"""The visits of a day or a week, grouped by day (every day of the window is listed, even one with
	no visit). Returns {"view", "start", "end", "days": [{"date", "visits"}]}."""
	first, after = _window(view, date)
	rows = _rows(first, after, user)
	days, day = [], first
	while day < after:
		days.append(
			{
				"date": str(day),
				"visits": [row for row in rows if getdate(row.visit_datetime) == day],
			}
		)
		day = add_days(day, 1)
	return {"view": view, "start": str(first), "end": str(add_days(after, -1)), "days": days}


def tomorrows_visits(now=None, user=None) -> dict:
	"""Tomorrow's visits to confirm, each with its confirmation status. A cancelled visit stays on the
	list, marked Cancelled. Returns {"date", "visits"}."""
	tomorrow = add_days(getdate(get_datetime(now) if now else now_datetime()), 1)
	return {"date": str(tomorrow), "visits": _rows(tomorrow, add_days(tomorrow, 1), user)}


# --- confirming and finishing a visit ---------------------------------------------------------------


def _open_visit(name):
	doc = frappe.get_doc(DOCTYPE, name)
	doc.check_permission("write")
	if doc.archived:
		frappe.throw(_("An archived visit cannot be changed."))
	if doc.status == DONE:
		frappe.throw(_("This visit is already done."))
	return doc


def confirm(name, confirmation_status, visit_datetime=None) -> dict:
	"""Set the confirmation status after the call the day before.

	Rescheduled needs the new date and time and moves the visit to it, and the agent is told again the day
	before the new date. Cancelled cancels the visit. Confirmed and Not confirmed change only the status."""
	if confirmation_status not in CONFIRMATIONS:
		frappe.throw(_("Choose one of: {0}.").format(", ".join(CONFIRMATIONS)))
	doc = _open_visit(name)
	if confirmation_status == RESCHEDULED:
		if not visit_datetime:
			frappe.throw(_("Enter the new date and time of the visit."), frappe.MandatoryError)
		doc.visit_datetime = get_datetime(visit_datetime)
	doc.confirmation_status = confirmation_status
	doc.status = CANCELLED if confirmation_status == CANCELLED else SCHEDULED
	doc.flags.ignore_permissions = True  # checked above
	doc.save()
	return visit_view(doc)


def complete(name, outcome, outcome_notes=None) -> dict:
	"""Mark a visit Done. It asks for the outcome. Returns the visit with "suggested_stage" (the next stage
	the outcome offers, or None when the lead is already on it or the outcome offers none) and "stage".
	The stage is offered here and moved by move_lead_stage when the agent accepts."""
	if outcome not in OUTCOME_STAGES:
		frappe.throw(_("Choose the outcome of the visit."), frappe.MandatoryError)
	doc = _open_visit(name)
	if doc.status == CANCELLED:
		frappe.throw(_("A cancelled visit cannot be marked done."))
	doc.status = DONE
	doc.visit_outcome = outcome
	doc.outcome_notes = (outcome_notes or "").strip() or None
	doc.flags.ignore_permissions = True
	doc.save()
	stage = frappe.db.get_value("Lead", doc.lead, "stage")
	offered = OUTCOME_STAGES[outcome]
	if not offered or offered == stage or not frappe.db.exists(pipeline.STAGE, offered):
		offered = None
	return {**visit_view(doc), "suggested_stage": offered, "stage": stage}


def visit_view(doc) -> dict:
	return {
		"name": doc.name,
		"lead": doc.lead,
		"project_name": doc.project_name,
		"visit_datetime": str(doc.visit_datetime),
		"agent": doc.agent,
		"status": doc.status,
		"confirmation_status": doc.confirmation_status,
		"outcome": doc.visit_outcome or "",
		"outcome_notes": doc.outcome_notes or "",
	}


def options(user=None) -> dict:
	"""What the booking form offers: the agents the user may book for, the outcomes and the confirmations.
	An Agent books for themselves, a Sales Manager for their team, a Company Admin for any active agent."""
	user = user or frappe.session.user
	agents = _agent_filter(user)
	if agents is None:
		from sellos.access.roles import AGENT, SALES_MANAGER

		agents = frappe.get_all(
			"Has Role", filters={"role": ["in", [AGENT, SALES_MANAGER]], "parenttype": "User"}, pluck="parent"
		)
	people = frappe.get_all(
		"User",
		filters={"name": ["in", sorted(set(agents))], "enabled": 1},
		fields=["name", "full_name"],
		order_by="full_name asc",
	)
	return {
		"agents": [{"name": p.name, "full_name": p.full_name or p.name} for p in people],
		"outcomes": [{"name": name, "next_stage": OUTCOME_STAGES[name] or ""} for name in OUTCOMES],
		"confirmations": list(CONFIRMATIONS),
		"statuses": list(STATUSES),
		"can_book_for_others": cint(len(agents or []) != 1),
	}
