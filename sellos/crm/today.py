"""The agent's Today screen (SOS-P1-26).

One answer for what a person does today, in four lists, each in time order:

* `follow_ups`: open follow ups due today or overdue (a follow up with only a day is due that day),
  soonest first, so the overdue ones lead.
* `new_leads`: leads on the New stage assigned to the person, the oldest first.
* `visits_today`: today's site visits that are not cancelled, by time.
* `visits_tomorrow`: tomorrow's site visits that are not cancelled, by time, with the confirmation status
  the agent sets after the call the day before (SOS-P1-25).

An Agent sees only their own records. A Sales Manager sees those of their team, and `agents` gives the
counts of each agent so the screen can show the team by agent. A Company Admin sees everyone's. The
counts at the top are the lengths of the lists, taken from the same lists, so they cannot differ.

Consent never blocks: each lead row carries its consent status as a warning and nothing here stops a call.
"""

import frappe
from frappe.utils import add_days, get_datetime, getdate, now_datetime

from sellos.crm import consent, follow_ups, pipeline, site_visits

SECTIONS = ("follow_ups", "new_leads", "visits_today", "visits_tomorrow")
MAX_NEW_LEADS = 200


def _scope(user):
	"""('own' | 'team' | 'all', the agents whose records the user sees, or None for everyone)."""
	from sellos.access import lead_permissions

	agents = site_visits._agent_filter(user)
	if agents is None:
		return "all", None
	scope = lead_permissions.scope_for(frappe.get_roles(user))
	return ("team" if scope == "team" else "own"), agents


def _follow_up_rows(user, agents, now) -> list[dict]:
	end_of_today = get_datetime(add_days(getdate(now), 1))
	rows = follow_ups.list_follow_ups(user=user, status="Open", now=now, everyone=True)
	return [
		row
		for row in rows
		if (agents is None or row.assigned_to in agents)
		and follow_ups.due_moment(row.due_at, row.due_date) < end_of_today
	]


def _new_lead_rows(agents) -> list[dict]:
	filters = {"archived": 0, "stage": pipeline.NEW}
	if agents is not None:
		filters["assigned_to"] = ["in", agents]
	rows = frappe.get_list(
		"Lead",
		filters=filters,
		fields=["name", "lead_title", "client", "assigned_to", "stage", "creation"],
		order_by="creation asc, name asc",
		limit_page_length=MAX_NEW_LEADS,
	)
	for row in rows:
		row["lead"] = row.name
	return rows


def _visit_rows(user, day) -> list[dict]:
	rows = site_visits._rows(day, add_days(day, 1), user)
	return [row for row in rows if row.status != site_visits.CANCELLED]


def _decorate(rows, key_agent) -> None:
	"""Add the lead's client, stage and consent warning to each row, and the agent's name."""
	leads = {}
	for lead in {row.lead for row in rows}:
		leads[lead] = frappe.db.get_value("Lead", lead, ["client", "stage", "lead_title"], as_dict=True) or {}
	names = {}
	for agent in {row.get(key_agent) for row in rows if row.get(key_agent)}:
		names[agent] = frappe.db.get_value("User", agent, "full_name") or agent
	statuses = {}
	for row in rows:
		info = leads.get(row.lead, {})
		row["client"] = info.get("client")
		row["stage"] = info.get("stage")
		row["lead_title"] = row.get("lead_title") or info.get("lead_title")
		row["agent"] = row.get(key_agent)
		row["agent_name"] = names.get(row.get(key_agent), "")
		if row.lead not in statuses:
			status = consent.compute_status(row.lead)
			level, message = consent.WARNINGS[status]
			statuses[row.lead] = (status, level, message)
		row["consent_status"], row["consent_warning"], row["consent_message"] = statuses[row.lead]


def today_view(user=None, now=None) -> dict:
	"""The four lists and their counts for the user, by agent for a Sales Manager.

	Returns {"date", "tomorrow", "scope", "counts", "follow_ups", "new_leads", "visits_today",
	"visits_tomorrow", "agents"}. `agents` has one entry per agent in the user's scope (name, full name and
	counts), so a manager sees who has what. `now` fixes the clock for a test."""
	user = user or frappe.session.user
	now = get_datetime(now) if now else now_datetime()
	day = getdate(now)
	scope, agents = _scope(user)
	lists = {
		"follow_ups": _follow_up_rows(user, agents, now),
		"new_leads": _new_lead_rows(agents),
		"visits_today": _visit_rows(user, day),
		"visits_tomorrow": _visit_rows(user, add_days(day, 1)),
	}
	for key, rows in lists.items():
		_decorate(rows, "assigned_to" if key in ("follow_ups", "new_leads") else "agent")
		for row in rows:
			for field in ("creation", "due_date", "due_at"):
				if row.get(field) is not None:
					row[field] = str(row[field])
	counts = {key: len(rows) for key, rows in lists.items()}
	counts["total"] = sum(counts.values())
	return {
		"date": str(day),
		"tomorrow": str(add_days(day, 1)),
		"scope": scope,
		"counts": counts,
		**lists,
		"agents": _agent_counts(lists, agents),
	}


def _agent_counts(lists, agents) -> list[dict]:
	"""Each agent's counts. A manager sees their team (every member, even one with nothing today); the
	rows of anyone else seen, such as the manager's own, are added."""
	seen = {row.agent for rows in lists.values() for row in rows if row.agent}
	people = sorted(seen | set(agents or []))
	result = []
	for person in people:
		counts = {key: sum(1 for row in rows if row.agent == person) for key, rows in lists.items()}
		counts["total"] = sum(counts.values())
		result.append(
			{
				"agent": person,
				"agent_name": frappe.db.get_value("User", person, "full_name") or person,
				"counts": counts,
			}
		)
	return result
