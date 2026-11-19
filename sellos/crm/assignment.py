"""Assigning and reassigning leads (SOS-P1-19).

Every new lead reaches an agent at once. `assign_new` runs when any Lead is inserted, so a lead made by
hand, by the website endpoint or by an import is assigned by the same rules, and each assignment is written
to the Lead Assignment log.

* The Company Admin keeps Lead Assignment Rules. They are tried from the lowest Order up. A Round robin
  rule matches every lead, a Source rule the leads from that source, a Locality rule the leads that want
  that locality. A rule names a team, and the team's active agents take the leads in turn.
* A lead no rule matches goes to the default team (SellOS Settings). With no default team, and no rule that
  finds an active agent, it stays unassigned.
* Round robin keeps a position on the Sales Team (`last_assigned`). It skips an agent who is deactivated
  and spreads leads evenly over the rest.
* A lead assigned by hand keeps the agent it was given. Reassigning, one lead or many, moves its open
  follow ups and its future site visits to the new agent, and notifies them (SOS-P1-23, on the lead save).
* Deactivating an agent hands every open lead, open follow up and future site visit to another agent.

Consent never blocks: nothing here looks at consent.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN
from sellos.crm.requirements import split_values

LOG = "Lead Assignment"
RULE = "Lead Assignment Rule"
TEAM = "Sales Team"
SETTINGS = "SellOS Settings"
RULE_TYPES = ("Round robin", "Source", "Locality")
RULE_METHOD, DEFAULT_METHOD, MANUAL_METHOD, BULK_METHOD, DEACTIVATION_METHOD = (
	"Rule",
	"Default team",
	"Manual",
	"Bulk",
	"Deactivation",
)
# A bulk reassignment moves at most this many leads in one call.
BULK_LIMIT = 500
CAN_TAKE_LEADS = frozenset({AGENT, CHANNEL_PARTNER, COMPANY_ADMIN})  # as Lead.CAN_BE_ASSIGNED


# --- who can take a lead ------------------------------------------------------------------------------


def can_take_leads(user) -> bool:
	"""An enabled user who may hold a lead (an agent, a channel partner or a Company Admin)."""
	if not user or not frappe.db.get_value("User", user, "enabled"):
		return False
	return bool(set(frappe.get_roles(user)) & CAN_TAKE_LEADS)


def check_assignee(user) -> None:
	if not can_take_leads(user):
		frappe.throw(_("{0} cannot be given leads: choose an active agent.").format(user or _("No one")))


def active_agents(team) -> list[str]:
	"""The team's agents who are enabled, in the order they were added."""
	members = frappe.get_all(
		"Sales Team Member",
		filters={"parenttype": TEAM, "parent": team},
		pluck="agent",
		order_by="idx asc",
	)
	return [agent for agent in members if can_take_leads(agent)]


def next_agent(team) -> str | None:
	"""The next active agent of the team in turn, and remember it. None when the team has none.

	The position is the last agent given a lead. The team row is locked, so two leads made at once take
	two different turns."""
	if not team or not frappe.db.exists(TEAM, team):
		return None
	agents = active_agents(team)
	if not agents:
		return None
	last = frappe.db.get_value(TEAM, team, "last_assigned", for_update=True)
	following = agents.index(last) + 1 if last in agents else 0
	agent = agents[following % len(agents)]
	frappe.db.set_value(TEAM, team, "last_assigned", agent, update_modified=False)
	return agent


def team_of(agent) -> str | None:
	return frappe.db.get_value("Sales Team Member", {"agent": agent, "parenttype": TEAM}, "parent")


# --- the rules ----------------------------------------------------------------------------------------


def rules() -> list[dict]:
	return frappe.get_all(
		RULE,
		filters={"enabled": 1},
		fields=["name", "rule_type", "source", "locality", "team", "priority"],
		order_by="priority asc, creation asc",
		limit_page_length=0,
	)


def default_team() -> str | None:
	return frappe.db.get_single_value(SETTINGS, "default_team") or None


def rule_matches(rule, source, localities) -> bool:
	if rule.rule_type == "Source":
		return bool(source) and rule.source == source
	if rule.rule_type == "Locality":
		wanted = (rule.locality or "").casefold()
		return bool(wanted) and wanted in {place.casefold() for place in localities}
	return True


def choose(source=None, localities=None) -> dict | None:
	"""Who a new lead goes to: {agent, method, rule, team}, or None when no rule and no default team has an
	active agent. Each rule that matches is tried in order, and one whose team has no active agent is passed over."""
	places = split_values(localities)
	for rule in rules():
		if rule_matches(rule, source, places):
			agent = next_agent(rule.team)
			if agent:
				return {"agent": agent, "method": RULE_METHOD, "rule": rule.name, "team": rule.team}
	team = default_team()
	agent = next_agent(team)
	if agent:
		return {"agent": agent, "method": DEFAULT_METHOD, "rule": None, "team": team}
	return None


def assign_new(lead) -> None:
	"""Run before a lead is inserted. A lead given an agent keeps it. Any other goes by the rules."""
	if lead.assigned_to:
		lead.flags.assignment = {"method": MANUAL_METHOD}
		return
	chosen = choose(lead.source, lead.get("preferred_localities"))
	if chosen:
		lead.assigned_to = chosen["agent"]
		lead.flags.assignment = chosen
		lead.flags.assigned_by_rule = True  # a Sales Manager's own team check does not apply to a rule


# --- the log and what moves with a lead --------------------------------------------------------------


def log(lead, old, new, method, rule=None, team=None, note=None) -> str:
	return (
		frappe.get_doc(
			{
				"doctype": LOG,
				"lead": lead,
				"from_agent": old or None,
				"to_agent": new or None,
				"method": method,
				"rule": rule,
				"team": team,
				"assigned_by": frappe.session.user,
				"note": note,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def move_work(lead, agent) -> dict:
	"""Give a lead's open follow ups and its future scheduled site visits to the agent."""
	tasks = frappe.get_all(
		"Lead Task",
		filters={"lead": lead, "archived": 0, "status": "Open", "assigned_to": ["!=", agent]},
		pluck="name",
	)
	visits = frappe.get_all(
		"Site Visit",
		filters={
			"lead": lead,
			"archived": 0,
			"status": "Scheduled",
			"visit_datetime": [">", now_datetime()],
			"agent": ["!=", agent],
		},
		pluck="name",
	)
	for name in tasks:
		frappe.db.set_value("Lead Task", name, "assigned_to", agent)
	for name in visits:
		frappe.db.set_value("Site Visit", name, "agent", agent)
	return {"tasks": len(tasks), "visits": len(visits)}


def on_lead_saved(lead) -> None:
	"""Run after a lead is saved. When its agent changed: log it, and move its open follow ups and future
	site visits to the new agent."""
	previous = lead.get_doc_before_save()
	old = previous.assigned_to if previous else None
	if lead.assigned_to == old:
		return
	info = lead.flags.assignment or {"method": MANUAL_METHOD}
	log(
		lead.name, old, lead.assigned_to, info["method"], info.get("rule"), info.get("team"), info.get("note")
	)
	if previous and lead.assigned_to:
		lead.flags.work_moved = move_work(lead.name, lead.assigned_to)
		lead.flags.assignment = None


# --- reassigning --------------------------------------------------------------------------------------


def reassign(names, agent, method=MANUAL_METHOD, note=None) -> dict:
	"""Give these leads to the agent. The user must be allowed to change each lead, and a Sales Manager may
	pick only an agent of their own team (the Lead's own check). It all happens or none of it does."""
	check_assignee(agent)
	moved, tasks, visits = [], 0, 0
	for name in names:
		doc = frappe.get_doc("Lead", name)
		doc.check_permission("write")
		if doc.assigned_to == agent:
			continue
		doc.assigned_to = agent
		doc.flags.assignment = {"method": method, "note": note}
		doc.flags.ignore_permissions = True  # checked above
		doc.save()
		work = doc.flags.work_moved or {"tasks": 0, "visits": 0}
		tasks, visits = tasks + work["tasks"], visits + work["visits"]
		moved.append(name)
	return {
		"assigned_to": agent,
		"moved": moved,
		"count": len(moved),
		"tasks_moved": tasks,
		"visits_moved": visits,
	}


def bulk_reassign(agent, leads=None, filters=None) -> dict:
	"""Reassign the listed leads, or every lead a list filter finds, to one agent. Only leads the user may
	see are found, and a filtered set larger than BULK_LIMIT is refused, not cut."""
	from sellos.crm import board

	if leads is not None:
		names = frappe.parse_json(leads) if isinstance(leads, str) else list(leads)
	else:
		given = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
		keys = {key: given[key] for key in board.FILTER_KEYS if key in given}
		names = [lead.name for lead in board.visible_leads(**keys)]
	names = list(dict.fromkeys(names))
	if not names:
		frappe.throw(_("There are no leads to reassign."))
	if len(names) > BULK_LIMIT:
		frappe.throw(_("Narrow the filters: at most {0} leads can be reassigned at once.").format(BULK_LIMIT))
	return reassign(names, agent, BULK_METHOD)


def assignable_agents() -> list[dict]:
	"""The agents the user may give leads to: every enabled agent for a Company Admin, the agents of their
	own teams for a Sales Manager."""
	from sellos.access.lead_permissions import team_members

	if COMPANY_ADMIN in frappe.get_roles() or "System Manager" in frappe.get_roles():
		emails = frappe.get_all("Has Role", filters={"role": AGENT, "parenttype": "User"}, pluck="parent")
	else:
		emails = team_members(frappe.session.user)
	emails = [email for email in dict.fromkeys(emails) if can_take_leads(email)]
	if not emails:
		return []
	return frappe.get_all(
		"User", filters={"name": ["in", emails]}, fields=["name", "full_name"], order_by="full_name asc"
	)


def history(lead) -> list[dict]:
	"""A lead's assignment log, newest first."""
	return frappe.get_all(
		LOG,
		filters={"lead": lead},
		fields=[
			"name",
			"creation",
			"from_agent",
			"to_agent",
			"method",
			"rule",
			"team",
			"assigned_by",
			"note",
		],
		order_by="creation desc, name desc",
		limit_page_length=0,
	)


# --- an agent leaves ----------------------------------------------------------------------------------


def open_work(email) -> dict:
	"""The open leads, open follow ups and future site visits held by a user."""
	stages = frappe.get_all("Pipeline Stage", filters={"stage_type": "Open"}, pluck="name")
	leads = (
		frappe.get_all(
			"Lead",
			filters={"assigned_to": email, "archived": 0, "stage": ["in", stages]},
			pluck="name",
			order_by="creation asc",
		)
		if stages
		else []
	)
	tasks = frappe.get_all(
		"Lead Task", filters={"assigned_to": email, "archived": 0, "status": "Open"}, pluck="name"
	)
	visits = frappe.get_all(
		"Site Visit",
		filters={
			"agent": email,
			"archived": 0,
			"status": "Scheduled",
			"visit_datetime": [">", now_datetime()],
		},
		pluck="name",
	)
	return {"leads": leads, "tasks": tasks, "visits": visits}


def _next_for(email, team, lead) -> str:
	"""The agent who takes one of a leaver's leads: the next of their team, else by the assignment rules."""
	agent = next_agent(team) if team else None
	if not agent:
		source, places = frappe.db.get_value("Lead", lead, ["source", "preferred_localities"])
		agent = (choose(source, places) or {}).get("agent")
	if not agent or agent == email:
		frappe.throw(_("There is no active agent to take this agent's leads. Choose one."))
	return agent


def hand_over(email, to=None, distribute=0) -> dict:
	"""Give everything a leaving agent holds to someone else, so nothing stays with an inactive user.

	`to` is one agent who takes it all. `distribute` shares the leads, in turn, among the active agents of
	the leaver's team, or by the assignment rules when they have no team. Call it after the user is disabled,
	so round robin skips them. Refuses, and changes nothing, when there is nobody to take the work."""
	work = open_work(email)
	if not (work["leads"] or work["tasks"] or work["visits"]):
		return {"leads": 0, "tasks": 0, "visits": 0}
	if to:
		check_assignee(to)
		if to == email:
			frappe.throw(_("Choose another agent to take the leads."))
	elif not cint(distribute):
		frappe.throw(_("Choose who takes this agent's leads."))
	team = team_of(email)
	fallback = to
	for name in work["leads"]:
		agent = to or _next_for(email, team, name)
		fallback = fallback or agent
		reassign([name], agent, DEACTIVATION_METHOD, _("{0} was deactivated.").format(email))
	for doctype, field, names in (
		("Lead Task", "assigned_to", work["tasks"]),
		("Site Visit", "agent", work["visits"]),
	):
		for name in names:  # a record on a lead the agent did not hold goes with that lead's agent
			owner = frappe.db.get_value("Lead", frappe.db.get_value(doctype, name, "lead"), "assigned_to")
			target = owner if owner != email and can_take_leads(owner) else fallback
			if not target:
				frappe.throw(
					_("There is no active agent to take this agent's follow ups and visits. Choose one.")
				)
			frappe.db.set_value(doctype, name, field, target)
	return {key: len(value) for key, value in work.items()}
