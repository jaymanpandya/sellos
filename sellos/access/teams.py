"""Sales teams (SOS-P1-18). A Company Admin creates teams, sets a manager and adds agents. An agent is
in at most one team, which the Sales Team DocType checks on every save. A Sales Manager reads the teams
they manage, through the permission query in `lead_permissions`, and changes nothing."""

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER

TEAM = "Sales Team"


def _users_with(role) -> list[dict]:
	emails = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	if not emails:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", emails], "enabled": 1},
		fields=["name", "full_name"],
		order_by="full_name asc",
	)


def _team_view(team) -> dict:
	people = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	return {
		"name": team.name,
		"team_name": team.team_name,
		"manager": team.manager,
		"manager_name": people.get(team.manager, team.manager),
		"members": [
			{"user": row.agent, "full_name": people.get(row.agent, row.agent)} for row in team.members
		],
	}


@sellos_api(COMPANY_ADMIN, SALES_MANAGER)
def list_teams():
	"""The teams the user may read: every team for a Company Admin, the teams they manage for a Sales
	Manager. A Company Admin also gets the managers and agents to pick from, and the team each agent is in."""
	names = frappe.get_list(TEAM, pluck="name", order_by="team_name asc", limit_page_length=0)
	result = {"teams": [_team_view(frappe.get_doc(TEAM, name)) for name in names]}
	if COMPANY_ADMIN in frappe.get_roles():
		taken = {m.agent: m.parent for m in frappe.get_all("Sales Team Member", fields=["agent", "parent"])}
		result["managers"] = _users_with(SALES_MANAGER)
		result["agents"] = [{**u, "team": taken.get(u.name)} for u in _users_with(AGENT)]
	return result


@sellos_api(COMPANY_ADMIN)
def save_team(name=None, values=None):
	"""Create a team, or change its manager and agents. `values` holds team_name, manager and members
	(a list of agent emails). An agent already in another team is refused."""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if name:
		doc = frappe.get_doc(TEAM, name)
		doc.check_permission("write")
	else:
		doc = frappe.new_doc(TEAM)
		doc.check_permission("create")
		doc.team_name = values.get("team_name")
	if "manager" in values:
		doc.manager = values["manager"]
	if "members" in values:
		members = values["members"]
		if isinstance(members, str):
			members = frappe.parse_json(members)
		doc.set("members", [{"agent": agent} for agent in members or []])
	doc.save() if name else doc.insert()
	return _team_view(doc)


@sellos_api(COMPANY_ADMIN)
def delete_team(name):
	"""Remove a team. Its agents stay agents, and their leads stay where they are."""
	frappe.get_doc(TEAM, name).check_permission("delete")
	frappe.delete_doc(TEAM, name)
	return {"deleted": name}
