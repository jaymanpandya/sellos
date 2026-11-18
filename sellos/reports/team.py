"""The report a Sales Manager reads for its own team (SOS-P1-18).

It counts the leads the reader may see, through `frappe.get_list`, so the lead permission rules decide
the numbers: a Sales Manager gets its team's leads and no other team's, a Company Admin gets all."""

from collections import Counter

import frappe

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN, SALES_MANAGER


@sellos_api(COMPANY_ADMIN, SALES_MANAGER)
def team_report():
	leads = frappe.get_list(
		"Lead", filters={"archived": 0}, fields=["assigned_to", "stage"], limit_page_length=0
	)
	by_agent = Counter(lead.assigned_to or "" for lead in leads)
	by_stage = Counter(lead.stage or "" for lead in leads)
	names = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	return {
		"total": len(leads),
		"by_agent": [
			{"agent": agent, "agent_name": names.get(agent, "Unassigned"), "leads": count}
			for agent, count in sorted(by_agent.items())
		],
		"by_stage": [{"stage": stage, "leads": count} for stage, count in sorted(by_stage.items())],
		"teams": frappe.get_list("Sales Team", pluck="name", order_by="team_name asc"),
	}
