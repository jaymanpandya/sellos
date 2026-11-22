"""Response time alerts and escalation (SOS-P7-13).

A Company Admin sets two limits in SellOS Settings:

* a new lead with no agent for more than N minutes (default 10), and
* an assigned lead with no call or activity logged within N minutes of its assignment (default 120).

`check_response_times` is the one function that does the work. The scheduler calls it every five minutes,
and a test calls it with a fixed `now`. It is safe to run again: each miss is one Response Alert, found
again by its lead, its limit and the moment it was counted from.

* A miss alerts the lead's agent (the Company Admin for an unassigned lead). If it is still missed after
  the same period again, the Sales Manager of the agent's team is alerted, or the Company Admin when the
  agent has no team (an unassigned lead goes to the Company Admin again).
* The Response Alert records the lead, the limit, the agent, when it was missed and when it was resolved,
  for SOS-P5-02's reports. A miss is resolved when the lead gets an agent, a call or an activity is
  logged, the lead is reassigned, closed or archived.
* An alert only tells. It never reassigns a lead, blocks anything or changes a stage.
* A lead is only counted for a week: a lead older than that when the limits are first set does not flood
  anyone. Only open leads are counted (a Won or Lost lead is not waiting for a reply).
* Consent never blocks: nothing here looks at consent.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, get_datetime, now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.crm import notifications

DOCTYPE = "Response Alert"
SETTINGS = "SellOS Settings"
UNASSIGNED = "Unassigned"
NO_CONTACT = "No contact"
DEFAULT_UNASSIGNED_MINUTES = 10
DEFAULT_CONTACT_MINUTES = 120
# The longest limit a Company Admin may set: two days. A miss and its escalation fit inside the window.
MAX_MINUTES = 2880
# A lead is counted for this many days after it was made or assigned.
WINDOW_DAYS = 7


# --- the settings -------------------------------------------------------------------------------------


def limits() -> tuple[int, int]:
	"""(minutes unassigned, minutes with no contact), each falling back to its default."""
	unassigned = cint(frappe.db.get_single_value(SETTINGS, "response_unassigned_minutes"))
	contact = cint(frappe.db.get_single_value(SETTINGS, "response_contact_minutes"))
	return (unassigned or DEFAULT_UNASSIGNED_MINUTES, contact or DEFAULT_CONTACT_MINUTES)


@sellos_api(COMPANY_ADMIN)
def get_response_limits():
	unassigned, contact = limits()
	return {"unassigned_minutes": unassigned, "contact_minutes": contact}


@sellos_api(COMPANY_ADMIN)
def save_response_limits(unassigned_minutes, contact_minutes):
	"""Save the two limits, each from 1 to 2880 minutes. A miss already recorded is kept as it was."""
	values = {}
	for key, label, raw in (
		("response_unassigned_minutes", _("unassigned"), unassigned_minutes),
		("response_contact_minutes", _("no contact"), contact_minutes),
	):
		minutes = cint(raw)
		if not 1 <= minutes <= MAX_MINUTES:
			frappe.throw(_("Enter the {0} limit in minutes, from 1 to {1}.").format(label, MAX_MINUTES))
		values[key] = minutes
	for key, minutes in values.items():
		frappe.db.set_single_value(SETTINGS, key, minutes)
	return get_response_limits()


# --- who is told --------------------------------------------------------------------------------------


def _enabled(users) -> list[str]:
	out = []
	for user in users:
		if user and user not in out and frappe.db.get_value("User", user, "enabled"):
			out.append(user)
	return out


def company_admins() -> list[str]:
	names = frappe.get_all("Has Role", filters={"role": COMPANY_ADMIN, "parenttype": "User"}, pluck="parent")
	return sorted(_enabled(names))


def team_manager(agent) -> str | None:
	"""The manager of the agent's sales team, or None when the agent has no team or the manager is gone."""
	if not agent:
		return None
	team = frappe.db.get_value("Sales Team Member", {"parenttype": "Sales Team", "agent": agent}, "parent")
	manager = frappe.db.get_value("Sales Team", team, "manager") if team else None
	return manager if _enabled([manager]) else None


def first_recipients(limit_type, agent) -> list[str]:
	if limit_type == NO_CONTACT and _enabled([agent]):
		return [agent]
	return company_admins()


def escalation_recipients(limit_type, agent) -> list[str]:
	if limit_type == NO_CONTACT:
		manager = team_manager(agent)
		if manager:
			return [manager]
	return company_admins()


def _tell(alert, lead_title, recipients, level, minutes) -> None:
	if alert["limit_type"] == UNASSIGNED:
		message = _("{0} has had no agent for {1} minutes.").format(lead_title, minutes)
	else:
		message = _("{0} has had no call or activity for {1} minutes since it was assigned.").format(
			lead_title, minutes
		)
	title = _("Lead waiting too long") if level == 1 else _("Lead still waiting: escalated")
	for user in recipients:
		notifications.notify(
			user,
			notifications.RESPONSE_MISSED,
			title,
			message,
			lead=alert["lead"],
			dedupe_key=f"{notifications.RESPONSE_MISSED}:{alert['name']}:{level}:{user}",
		)


# --- what the clock finds -----------------------------------------------------------------------------


def _open_stages() -> list[str]:
	return frappe.get_all("Pipeline Stage", filters={"stage_type": "Open"}, pluck="name")


def _is_open(stage, open_stages) -> bool:
	return not stage or stage in open_stages


def assigned_on(lead, agent):
	"""When the lead was last given to this agent, from the assignment log."""
	return frappe.db.get_value(
		"Lead Assignment", {"lead": lead, "to_agent": agent}, "creation", order_by="creation desc"
	)


def first_contact(lead, since, until):
	"""The first call or activity logged for the lead from `since` to `until`, or None."""
	found = []
	activity = frappe.db.get_value(
		"Lead Activity",
		{"lead": lead, "archived": 0, "activity_date": ["between", [since, until]]},
		"activity_date",
		order_by="activity_date asc",
	)
	call = frappe.db.get_value(
		"Call Log",
		{"lead": lead, "started_on": ["between", [since, until]]},
		"started_on",
		order_by="started_on asc",
	)
	for value in (activity, call):
		if value:
			found.append(get_datetime(value))
	return min(found) if found else None


def _record(lead, limit_type, agent, counted_from, minutes, now):
	"""Make the one Response Alert of this miss and tell the first recipients. Returns it, or None when it
	already exists."""
	counted_from = get_datetime(counted_from)
	if frappe.db.exists(DOCTYPE, {"lead": lead.name, "limit_type": limit_type, "counted_from": counted_from}):
		return None
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"lead": lead.name,
			"limit_type": limit_type,
			"agent": agent,
			"counted_from": counted_from,
			"missed_on": add_to_date(counted_from, minutes=minutes),
			"escalation_level": 1,
		}
	).insert(ignore_permissions=True)
	_tell(doc.as_dict(), lead.lead_title, first_recipients(limit_type, agent), 1, minutes)
	return doc


def _find_unassigned(now, minutes, open_stages) -> int:
	made = 0
	leads = frappe.get_all(
		"Lead",
		filters=[
			["assigned_to", "is", "not set"],
			["archived", "=", 0],
			["creation", "<=", add_to_date(now, minutes=-minutes)],
			["creation", ">=", add_days(now, -WINDOW_DAYS)],
		],
		fields=["name", "lead_title", "stage", "creation"],
		limit_page_length=0,
	)
	for lead in leads:
		if _is_open(lead.stage, open_stages) and _record(lead, UNASSIGNED, None, lead.creation, minutes, now):
			made += 1
	return made


def _find_uncontacted(now, minutes, open_stages) -> int:
	made = 0
	since_limit = add_to_date(now, minutes=-minutes)
	candidates = frappe.get_all(
		"Lead Assignment",
		filters=[
			["to_agent", "is", "set"],
			["creation", "<=", since_limit],
			["creation", ">=", add_days(now, -WINDOW_DAYS)],
		],
		pluck="lead",
		distinct=True,
		limit_page_length=0,
	)
	for name in candidates:
		lead = frappe.db.get_value(
			"Lead", name, ["name", "lead_title", "stage", "assigned_to", "archived"], as_dict=True
		)
		if not lead or lead.archived or not lead.assigned_to or not _is_open(lead.stage, open_stages):
			continue
		since = assigned_on(lead.name, lead.assigned_to)
		if not since or get_datetime(since) > since_limit:
			continue  # assigned again since: the clock restarted
		if first_contact(lead.name, since, now):
			continue
		if _record(lead, NO_CONTACT, lead.assigned_to, since, minutes, now):
			made += 1
	return made


# --- resolving and escalating -------------------------------------------------------------------------


def _resolve(alert, when, how) -> None:
	frappe.db.set_value(
		DOCTYPE, alert.name, {"resolved_on": get_datetime(when), "resolution": how}, update_modified=False
	)


def _resolution(alert, now, open_stages):
	"""(when, how) when the alert's limit is no longer missed, else None."""
	lead = frappe.db.get_value("Lead", alert.lead, ["assigned_to", "archived", "stage"], as_dict=True)
	if not lead or lead.archived:
		return now, "Archived"
	if alert.limit_type == UNASSIGNED:
		if lead.assigned_to:
			given = frappe.db.get_value(
				"Lead Assignment",
				{"lead": alert.lead, "to_agent": lead.assigned_to, "creation": [">=", alert.counted_from]},
				"creation",
				order_by="creation asc",
			)
			return given or now, "Assigned"
	elif lead.assigned_to != alert.agent:
		return assigned_on(alert.lead, lead.assigned_to) or now, "Reassigned"
	else:
		contact = first_contact(alert.lead, alert.counted_from, now)
		if contact:
			return contact, "Contacted"
	if not _is_open(lead.stage, open_stages):
		return now, "Closed"
	return None


def _resolve_open(now, open_stages) -> int:
	done = 0
	for alert in frappe.get_all(
		DOCTYPE,
		filters={"resolved_on": ["is", "not set"]},
		fields=["name", "lead", "limit_type", "agent", "counted_from"],
		limit_page_length=0,
	):
		found = _resolution(alert, now, open_stages)
		if found:
			_resolve(alert, *found)
			done += 1
	return done


def _escalate(now, unassigned_minutes, contact_minutes) -> int:
	done = 0
	for alert in frappe.get_all(
		DOCTYPE,
		filters={"resolved_on": ["is", "not set"], "escalation_level": 1},
		fields=["name", "lead", "limit_type", "agent", "missed_on"],
		limit_page_length=0,
	):
		minutes = unassigned_minutes if alert.limit_type == UNASSIGNED else contact_minutes
		if now < add_to_date(alert.missed_on, minutes=minutes):
			continue
		recipients = escalation_recipients(alert.limit_type, alert.agent)
		frappe.db.set_value(
			DOCTYPE,
			alert.name,
			{"escalation_level": 2, "escalated_on": now, "escalated_to": ", ".join(recipients)},
			update_modified=False,
		)
		_tell(alert, frappe.db.get_value("Lead", alert.lead, "lead_title"), recipients, 2, minutes * 2)
		done += 1
	return done


def check_response_times(now=None) -> dict:
	"""Find the misses, alert, escalate and resolve. `now` is the clock a test fixes. Returns how many
	misses were found, escalated and resolved."""
	now = get_datetime(now) if now else now_datetime()
	unassigned_minutes, contact_minutes = limits()
	open_stages = _open_stages()
	resolved = _resolve_open(now, open_stages)
	missed = _find_unassigned(now, unassigned_minutes, open_stages) + _find_uncontacted(
		now, contact_minutes, open_stages
	)
	escalated = _escalate(now, unassigned_minutes, contact_minutes)
	return {"missed": missed, "escalated": escalated, "resolved": resolved}
