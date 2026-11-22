"""The pipeline board and the lead list filters (SOS-P1-24).

One function, `visible_leads`, finds the leads for both views, so the list and the board always agree.
It starts from `frappe.get_list`, which applies the user's lead permissions (an Agent sees their own,
a Sales Manager their team's, a Channel Partner their own leads), and then narrows by the filters. The
filters combine: a lead must satisfy every one given.

Last contacted is the latest Call, WhatsApp, Email or Meeting activity (a Note is not a contact). A lead
is untouched when it has had no activity of any kind, and was not made, within UNTOUCHED_DAYS.

Consent never blocks: the consent status is a filter and a warning on the card, and a card moves to any
stage whatever it is (SOS-P1-07, `pipeline.move_lead`).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, today

from sellos.crm import consent, follow_ups
from sellos.crm import pipeline as pipelines
from sellos.crm.requirements import REQUIREMENT_FIELDS, has_filters, matches, requirements_view

# A lead with no activity for this many days is marked untouched on the list and the board.
UNTOUCHED_DAYS = 7
CONTACT_TYPES = ("Call", "WhatsApp", "Email", "Meeting")
FILTER_KEYS = (
	"search",
	"stage",
	"assigned_to",
	"team",
	"source",
	"consent_status",
	"budget_min",
	"budget_max",
	"configuration",
	"locality",
	"timeline",
	"last_contacted_from",
	"last_contacted_to",
	"untouched",
	"follow_up",
	"sort",
)


def card_budget(lead) -> float:
	"""What a lead is worth to the column total: the top of its budget, or its lower figure when only that
	is given, in rupees. A lead with no budget counts nothing."""
	return flt(lead.get("budget_to")) or flt(lead.get("budget_from")) or 0.0


def _activity_dates(names) -> tuple[dict, dict]:
	"""({lead: last contact}, {lead: last activity of any kind}) for these leads, in one query."""
	last_contact, last_any = {}, {}
	if not names:
		return last_contact, last_any
	rows = frappe.get_all(
		"Lead Activity",
		filters={"lead": ["in", names], "archived": 0},
		fields=["lead", "activity_type", {"MAX": "activity_date", "as": "last_on"}],
		group_by="lead, activity_type",
		limit_page_length=0,
	)
	for row in rows:
		when = get_datetime(row.last_on)
		if row.activity_type in CONTACT_TYPES and when > last_contact.get(row.lead, when.min):
			last_contact[row.lead] = when
		if when > last_any.get(row.lead, when.min):
			last_any[row.lead] = when
	return last_contact, last_any


def _team_agents(team):
	return frappe.get_all("Sales Team Member", filters={"parent": team}, pluck="agent")


def pipeline_name(pipeline=None) -> str:
	pipeline = pipeline or pipelines.BUYER
	if pipeline not in pipelines.PIPELINES:
		frappe.throw(_("The pipeline is Buyer or Seller."))
	return pipeline


def visible_leads(
	search=None,
	stage=None,
	assigned_to=None,
	team=None,
	source=None,
	consent_status=None,
	budget_min=None,
	budget_max=None,
	configuration=None,
	locality=None,
	timeline=None,
	last_contacted_from=None,
	last_contacted_to=None,
	untouched=0,
	include_archived=0,
	follow_up=None,
	sort=None,
	now=None,
	pipeline=None,
) -> list[dict]:
	"""The leads the user may see that satisfy every filter given, newest change first, each with its
	client name, consent status, requirements, last contact and untouched mark.

	SOS-P1-22: each lead also carries its next open follow up (see sellos.crm.follow_ups.annotate).
	`follow_up` keeps the leads whose follow up is overdue, who have one open, who have none, or who are
	flagged untouched for having none. `sort="next_follow_up"` lists the soonest follow up first, the
	overdue ones leading, and the leads with none last. `now` fixes the clock for a test."""
	follow_ups.check_filter(follow_up, sort)
	filters = {} if cint(include_archived) else {"archived": 0}
	# SOS-P4-04: the buyer screens show the Buyer pipeline unless a pipeline is asked for.
	filters["pipeline"] = pipeline_name(pipeline)
	for field, value in (("stage", stage), ("assigned_to", assigned_to), ("source", source)):
		if value:
			filters[field] = value
	if team:
		agents = _team_agents(team)
		if assigned_to:  # both given: the agent must be in the team
			agents = [assigned_to] if assigned_to in agents else []
		if not agents:
			return []
		filters["assigned_to"] = ["in", agents]
	if isinstance(configuration, str) and configuration.startswith("["):
		configuration = frappe.parse_json(configuration)
	requirement_filters = {
		"budget_min": budget_min,
		"budget_max": budget_max,
		"configuration": configuration,
		"locality": locality,
		"timeline": timeline,
	}
	leads = frappe.get_list(
		"Lead",
		filters=filters,
		or_filters=[[f, "like", f"%{search}%"] for f in ("lead_title", "source", "campaign")]
		if search
		else [],
		fields=[
			"name",
			"lead_title",
			"client",
			"source",
			"campaign",
			"assigned_to",
			"stage",
			"archived",
			"modified",
			"creation",
			*REQUIREMENT_FIELDS,
		],
		order_by="modified desc",
		limit_page_length=0,
	)
	if has_filters(**requirement_filters):
		leads = [lead for lead in leads if matches(lead, **requirement_filters)]
	names = [lead.name for lead in leads]
	last_contact, last_any = _activity_dates(names)
	clients = dict(
		frappe.get_all(
			"Client",
			filters={"name": ["in", [lead.client for lead in leads]]},
			fields=["name", "client_name"],
			as_list=True,
			limit_page_length=0,
		)
		if leads
		else []
	)
	follow_ups.annotate(leads, now=now)
	cutoff = get_datetime(add_days(now_datetime(), -UNTOUCHED_DAYS))
	start = getdate(last_contacted_from) if last_contacted_from else None
	end = getdate(last_contacted_to) if last_contacted_to else None
	result = []
	for lead in leads:
		contacted = last_contact.get(lead.name)
		if start and not (contacted and contacted.date() >= start):
			continue
		if end and contacted and contacted.date() > end:
			continue  # a lead never contacted was not contacted by that date either
		touched = max(last_any.get(lead.name, cutoff.min), get_datetime(lead.creation))
		if follow_up and not follow_ups.matches_filter(lead, follow_up):
			continue
		lead["untouched"] = touched < cutoff
		if cint(untouched) and not lead["untouched"]:
			continue
		lead["consent_status"] = consent.compute_status(lead.name)
		if consent_status and lead["consent_status"] != consent_status:
			continue
		lead["consent_warning"] = consent.WARNINGS[lead["consent_status"]][0]
		lead["client_name"] = clients.get(lead.client)
		lead["requirements"] = requirements_view(lead)
		lead["last_contacted"] = contacted
		lead["budget"] = card_budget(lead)
		result.append(lead)
	return follow_ups.sort_by_next_follow_up(result) if sort == "next_follow_up" else result


def board(pipeline=None, **filters) -> dict:
	"""One column per stage of the pipeline, in order, with the leads in it, the count and the total
	budget. A lead on a stage the pipeline no longer has is not shown."""
	pipeline = pipeline_name(pipeline)
	leads = visible_leads(pipeline=pipeline, **filters)
	by_stage = {}
	for lead in leads:
		by_stage.setdefault(lead.stage, []).append(lead)
	columns = []
	for stage in pipelines.list_stages(pipeline):
		cards = by_stage.get(stage["name"], [])
		columns.append(
			{
				"stage": stage["name"],
				"label": stage["label"],
				"stage_type": stage["stage_type"],
				"count": len(cards),
				"total_budget": sum(card["budget"] for card in cards),
				"leads": cards,
			}
		)
	return {
		"columns": columns,
		"total": sum(column["count"] for column in columns),
		"untouched_days": UNTOUCHED_DAYS,
		"follow_up_untouched_days": follow_ups.untouched_days(),
		"today": today(),
	}


def filter_options() -> dict:
	"""What the filter boxes offer. Agents are the ones who hold leads the user may see, so an Agent
	is offered only themselves and a Sales Manager only their team. Teams are the ones the user may read."""
	leads = frappe.get_list("Lead", filters={"archived": 0}, fields=["assigned_to"], limit_page_length=0)
	emails = sorted({lead.assigned_to for lead in leads if lead.assigned_to})
	people = {
		u.name: u.full_name
		for u in frappe.get_all("User", filters={"name": ["in", emails]}, fields=["name", "full_name"])
	}
	teams = []
	if frappe.has_permission("Sales Team", "read"):
		teams = frappe.get_list("Sales Team", pluck="name", order_by="team_name asc", limit_page_length=0)
	return {
		"agents": [{"name": email, "full_name": people.get(email) or email} for email in emails],
		"teams": [
			{"name": name, "team_name": frappe.db.get_value("Sales Team", name, "team_name")}
			for name in teams
		],
		"consent_statuses": list(consent.STATUSES),
		"untouched_days": UNTOUCHED_DAYS,
		"follow_up_untouched_days": follow_ups.untouched_days(),
	}
