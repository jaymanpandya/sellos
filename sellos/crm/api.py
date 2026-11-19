"""The CRM API (P1.06). Every method declares its roles with @sellos_api and is in the matrix.

Data rules are enforced by the DocType permissions and `sellos/access/lead_permissions.py`. These
methods never skip them, except to write the phone fields, which sit at permission level 1: the
method checks the user's own create or write permission first, then writes the allowed fields.
Phone numbers are returned in full only to a Company Admin.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN, SALES_MANAGER
from sellos.crm import (
	assignment,
	board,
	call_outcomes,
	consent,
	duplicates,
	follow_ups,
	lead_import,
	lead_sources,
	notifications,
	pipeline,
	site_visits,
	today,
)
from sellos.crm.requirements import REQUIREMENT_FIELDS, join_values, requirements_view

# SOS-P1-18: a Sales Manager works like an Agent, on the leads of their team, with masked phone numbers.
READERS = (AGENT, CHANNEL_PARTNER, COMPANY_ADMIN, SALES_MANAGER)
LOGGERS = (
	AGENT,
	COMPANY_ADMIN,
	SALES_MANAGER,
)  # may log activities, tasks and visits. A partner only reads them.

CLIENT_FIELDS = (
	"client_name",
	"client_type",
	"email",
	"city",
	"country_of_residence",
	"phone",
	"overseas_phone",
)
LEAD_FIELDS = ("client", "source", "campaign", "assigned_to", "notes", *REQUIREMENT_FIELDS)
ACTIVITY_FIELDS = ("lead", "activity_type", "activity_date", "notes")
TASK_FIELDS = ("lead", "title", "due_date", "due_at", "status", "assigned_to", "notes")
VISIT_FIELDS = ("lead", "project_name", "visit_datetime", "agent", "status", "notes")
FOLLOW_UP_KEYS = (
	"next_follow_up",
	"next_follow_up_name",
	"next_follow_up_title",
	"next_follow_up_has_time",
	"follow_up_state",
	"open_follow_ups",
	"follow_up_untouched",
)
MULTI_VALUE_FIELDS = ("configuration", "preferred_localities")
ARCHIVABLE = ("Client", "Lead", "Lead Activity", "Lead Task", "Site Visit")


def _values(values, allowed):
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	return {key: values[key] for key in allowed if key in values}


def _sees_phone() -> bool:
	return COMPANY_ADMIN in frappe.get_roles() or "System Manager" in frappe.get_roles()


def _save(doctype, name, values, allowed):
	"""Create or update with the user's own permission checked, then write the allowed fields."""
	values = _values(values, allowed)
	for field in MULTI_VALUE_FIELDS:
		if field in values:
			values[field] = join_values(values[field])
	if name:
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("write")
		doc.update(values)
		doc.flags.ignore_permissions = True  # checked above. Needed for the level 1 phone fields.
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": doctype, **values})
		doc.check_permission("create")
		doc.flags.ignore_permissions = True
		doc.insert()
	return doc


def log_full_number_shown(names) -> None:
	"""Record that the current user was shown the full phone numbers of these clients (P1.06B).

	One Access Log row per call, so a list of 100 clients writes one row. It holds who, when and
	which clients, never a number."""
	names = sorted(set(names))
	if not names:
		return
	frappe.get_doc(
		{
			"doctype": "Access Log",
			"export_from": "Client",
			"user": frappe.session.user,
			"method": "Full phone number shown",
			"reference_document": names[0],
			"filters": frappe.as_json(names),
			"timestamp": now_datetime(),
		}
	).insert(ignore_permissions=True)


def client_view(doc, log=True) -> dict:
	"""A client as the current user may see it. Only a Company Admin gets the full phone numbers.

	A full number shown is logged (P1.06B). A caller that shows many clients passes log=False and
	calls log_full_number_shown once for all of them."""
	view = {
		"name": doc.name,
		"client_name": doc.client_name,
		"client_type": doc.client_type,
		"email": doc.email,
		"city": doc.city,
		"country_of_residence": doc.country_of_residence,
		"phone": doc.phone_masked,
		"overseas_phone": doc.overseas_phone_masked,
		"archived": cint(doc.archived),
	}
	if _sees_phone():
		view["phone"] = doc.phone
		view["overseas_phone"] = doc.overseas_phone
		if log and (doc.phone or doc.overseas_phone):
			log_full_number_shown([doc.name])
	return view


def _search(term, fields):
	return [[field, "like", f"%{term}%"] for field in fields] if term else []


@sellos_api(*READERS)
def list_clients(search=None, include_archived=0):
	filters = {} if cint(include_archived) else {"archived": 0}
	names = frappe.get_list(
		"Client",
		filters=filters,
		or_filters=_search(search, ("client_name", "email", "city")),
		pluck="name",
		order_by="modified desc",
		limit_page_length=100,
	)
	docs = [frappe.get_doc("Client", name) for name in names]
	if _sees_phone():
		log_full_number_shown([d.name for d in docs if d.phone or d.overseas_phone])
	return [client_view(doc, log=False) for doc in docs]


def _match_view(match) -> dict:
	"""One duplicate as the current user may see it (SOS-P1-16).

	A client the user can read is shown with the leads they can read. One they cannot read is only
	reported as existing, with the masked number: no name, no email, no leads, no full number. Only a
	Company Admin gets full numbers, and that is logged like every other full number shown."""
	name = match["name"]
	readable = frappe.has_permission("Client", "read", doc=name)
	view = {"name": name, "matched_on": match["matched_on"], "visible": bool(readable), "leads": []}
	if not readable:
		masked = frappe.db.get_value("Client", name, ["phone_masked", "overseas_phone_masked"], as_dict=True)
		view.update(phone=masked.phone_masked, overseas_phone=masked.overseas_phone_masked, can_add=False)
		return view
	view.update(client_view(frappe.get_doc("Client", name), log=False), name=name, can_add=True)
	view["leads"] = frappe.get_list(
		"Lead",
		filters={"client": name, "archived": 0},
		fields=["name", "lead_title", "source", "assigned_to"],
		order_by="modified desc",
		limit_page_length=20,
	)
	return view


@sellos_api(*LOGGERS)
def find_duplicates(phone=None, overseas_phone=None, email=None, exclude=None):
	"""The clients that already have this phone, overseas phone or email (SOS-P1-16).

	Used by the screens while a lead or client is entered. It calls duplicates.find_matches, the
	function the website endpoint and the import call too."""
	matches = duplicates.find_matches(phone, overseas_phone, email, exclude=exclude)
	views = [_match_view(match) for match in matches]
	if _sees_phone():
		log_full_number_shown(
			[v["name"] for v in views if v["visible"] and (v["phone"] or v["overseas_phone"])]
		)
	return views


@sellos_api(COMPANY_ADMIN)
def merge_clients(keep, merge):
	"""Merge the client `merge` into `keep` (SOS-P1-16). Leads, and with them their activities, tasks
	and site visits, move to `keep`. `merge` is archived, never deleted, and the merge is logged."""
	frappe.get_doc("Client", keep).check_permission("write")
	frappe.get_doc("Client", merge).check_permission("write")
	result = duplicates.merge_clients(keep, merge)
	return {"kept": result["kept"], "merged": result["merged"], "leads_moved": len(result["leads_moved"])}


@sellos_api(*READERS)
def save_client(name=None, values=None):
	return client_view(_save("Client", name, values, CLIENT_FIELDS))


@sellos_api(*READERS)
def list_leads(
	search=None,
	include_archived=0,
	budget_min=None,
	budget_max=None,
	configuration=None,
	locality=None,
	timeline=None,
	stage=None,
	assigned_to=None,
	team=None,
	source=None,
	consent_status=None,
	last_contacted_from=None,
	last_contacted_to=None,
	untouched=0,
	follow_up=None,
	sort=None,
):
	"""The leads the user may see, up to 100, narrowed by every filter given (SOS-P1-24 and SOS-P1-15):
	stage, agent, team, source, consent status, budget range, configuration, locality, timeline, last
	contacted dates and untouched. See sellos.crm.board.visible_leads. Each lead says whether it is untouched.
	SOS-P1-22: `follow_up` (overdue, open, none or untouched) filters by the lead's follow up, `sort`
	("next_follow_up") lists the soonest first, and each lead carries its next open follow up."""
	leads = board.visible_leads(
		search=search,
		include_archived=include_archived,
		budget_min=budget_min,
		budget_max=budget_max,
		configuration=configuration,
		locality=locality,
		timeline=timeline,
		stage=stage,
		assigned_to=assigned_to,
		team=team,
		source=source,
		consent_status=consent_status,
		last_contacted_from=last_contacted_from,
		last_contacted_to=last_contacted_to,
		untouched=untouched,
		follow_up=follow_up,
		sort=sort,
	)[:100]
	for lead in leads:
		tasks = frappe.get_all(
			"Lead Task",
			filters={"lead": lead.name, "archived": 0, "status": "Open"},
			fields=["due_date", "due_at"],
		)
		lead["open_tasks"] = len(tasks)
		lead["overdue_tasks"] = sum(
			follow_ups.due_state(t.due_at, t.due_date) == follow_ups.OVERDUE for t in tasks
		)
	return leads


@sellos_api(*READERS)
def get_board(
	search=None,
	budget_min=None,
	budget_max=None,
	configuration=None,
	locality=None,
	timeline=None,
	stage=None,
	assigned_to=None,
	team=None,
	source=None,
	consent_status=None,
	last_contacted_from=None,
	last_contacted_to=None,
	untouched=0,
	follow_up=None,
	sort=None,
):
	"""The pipeline board (SOS-P1-24): one column per stage with the leads the user may see, the count
	and the total budget, under the same filters as the list. A card moves with move_lead_stage."""
	return board.board(
		search=search,
		budget_min=budget_min,
		budget_max=budget_max,
		configuration=configuration,
		locality=locality,
		timeline=timeline,
		stage=stage,
		assigned_to=assigned_to,
		team=team,
		source=source,
		consent_status=consent_status,
		last_contacted_from=last_contacted_from,
		last_contacted_to=last_contacted_to,
		untouched=untouched,
		follow_up=follow_up,
		sort=sort,
	)


@sellos_api(*READERS)
def lead_filter_options():
	"""The agents, teams and consent statuses the list and board filters offer the user (SOS-P1-24)."""
	return board.filter_options()


@sellos_api(*READERS)
def list_lead_sources(include_disabled=0):
	"""The lead sources for a picker (SOS-P1-20). Only a Company Admin is shown, and may manage, the disabled ones."""
	manage = COMPANY_ADMIN in frappe.get_roles()
	sources = lead_sources.list_sources(include_disabled=bool(cint(include_disabled)) and manage)
	return {"sources": sources, "can_manage": manage}


@sellos_api(COMPANY_ADMIN)
def save_lead_source(name=None, values=None):
	"""Add a source, or enable or disable one. A source keeps its name, because reports group by it."""
	values = _values(values, ("source_name", "enabled"))
	if name:
		doc = frappe.get_doc("Lead Source", name)
		doc.check_permission("write")
		if "enabled" in values:
			doc.enabled = cint(values["enabled"])
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Lead Source", **values})
		doc.check_permission("create")
		doc.insert()
	return {"name": doc.name, "enabled": cint(doc.enabled)}


@sellos_api(COMPANY_ADMIN)
def delete_lead_source(name):
	"""Delete a source no lead uses. A source in use is refused, and is disabled instead."""
	doc = frappe.get_doc("Lead Source", name)
	doc.check_permission("delete")
	lead_sources.ensure_deletable(name)
	frappe.delete_doc("Lead Source", name)
	return {"deleted": name}


@sellos_api(*READERS)
def list_stages():
	"""The buyer pipeline's stages in order, each with its kind and how many leads it holds (SOS-P1-07)."""
	return pipeline.list_stages()


@sellos_api(*LOGGERS)
def move_lead_stage(lead, stage, lost_reason=None):
	"""Move a lead to any stage (SOS-P1-07), whatever its consent status, and log the move. Moving it to
	Contacted without a live Consent Record returns a warning, writes it to the stage change log and
	goes ahead. A stage that does not exist is refused, and so is a Lost stage with no lost reason
	from the Company Admin's list (SOS-P1-21)."""
	_writable_lead(lead)
	return pipeline.move_lead(lead, stage, lost_reason=lost_reason)


@sellos_api(*LOGGERS)
def list_call_outcomes(include_disabled=0):
	"""The call outcomes for a picker (SOS-P1-21): each with its suggested stage and whether it needs a
	follow up. SOS-P2-07's outcome form and SOS-P2-05's Call Log read this list. Only a Company Admin
	is shown, and may manage, the disabled ones."""
	manage = COMPANY_ADMIN in frappe.get_roles()
	outcomes = call_outcomes.list_outcomes(include_disabled=bool(cint(include_disabled)) and manage)
	return {"outcomes": outcomes, "can_manage": manage}


@sellos_api(COMPANY_ADMIN)
def save_call_outcome(name=None, values=None):
	"""Add an outcome, or change whether it is enabled, needs a follow up or suggests a stage. An outcome
	keeps its name, because reports group by it."""
	values = _values(values, ("outcome_name", "enabled", "needs_follow_up", "suggested_stage"))
	if name:
		doc = frappe.get_doc("Call Outcome", name)
		doc.check_permission("write")
		for field in ("enabled", "needs_follow_up"):
			if field in values:
				setattr(doc, field, cint(values[field]))
		if "suggested_stage" in values:
			doc.suggested_stage = values["suggested_stage"] or None
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Call Outcome", **values})
		doc.check_permission("create")
		doc.insert()
	return {
		"name": doc.name,
		"enabled": cint(doc.enabled),
		"needs_follow_up": cint(doc.needs_follow_up),
		"suggested_stage": doc.suggested_stage or "",
	}


@sellos_api(COMPANY_ADMIN)
def delete_call_outcome(name):
	"""Delete an outcome no call used. One in use is refused, and is disabled instead."""
	doc = frappe.get_doc("Call Outcome", name)
	doc.check_permission("delete")
	call_outcomes.ensure_outcome_deletable(name)
	frappe.delete_doc("Call Outcome", name)
	return {"deleted": name}


@sellos_api(*LOGGERS)
def list_lost_reasons(include_disabled=0):
	"""The lost reasons for the move to a Lost stage (SOS-P1-21). Only a Company Admin is shown, and may
	manage, the disabled ones."""
	manage = COMPANY_ADMIN in frappe.get_roles()
	reasons = call_outcomes.list_lost_reasons(include_disabled=bool(cint(include_disabled)) and manage)
	return {"lost_reasons": reasons, "can_manage": manage}


@sellos_api(COMPANY_ADMIN)
def save_lost_reason(name=None, values=None):
	"""Add a lost reason, or enable or disable one. A reason keeps its name, because reports group by it."""
	values = _values(values, ("reason_name", "enabled"))
	if name:
		doc = frappe.get_doc("Lost Reason", name)
		doc.check_permission("write")
		if "enabled" in values:
			doc.enabled = cint(values["enabled"])
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Lost Reason", **values})
		doc.check_permission("create")
		doc.insert()
	return {"name": doc.name, "enabled": cint(doc.enabled)}


@sellos_api(COMPANY_ADMIN)
def delete_lost_reason(name):
	"""Delete a lost reason no lead used. One in use is refused, and is disabled instead."""
	doc = frappe.get_doc("Lost Reason", name)
	doc.check_permission("delete")
	call_outcomes.ensure_reason_deletable(name)
	frappe.delete_doc("Lost Reason", name)
	return {"deleted": name}


@sellos_api(*LOGGERS)
def log_call(
	lead,
	outcome,
	notes=None,
	duration_seconds=None,
	follow_up_at=None,
	stage=None,
	lost_reason=None,
	called_at=None,
):
	"""Log a call made by hand on a lead (SOS-P1-21): a Call activity with its outcome, notes and
	duration. An outcome that needs a follow up needs `follow_up_at` and creates the follow up. `stage`
	is the agent's own choice of any stage, and the outcome's suggested stage comes back as
	`suggested_stage` to be offered, never applied. Whatever the lead's consent status, it is logged."""
	_writable_lead(lead)
	return call_outcomes.log_call(
		lead, outcome, notes, duration_seconds, follow_up_at, stage, lost_reason, called_at
	)


@sellos_api(COMPANY_ADMIN, SALES_MANAGER)
def reassign_lead(lead, assigned_to, note=None):
	"""Give a lead to another agent (SOS-P1-18, SOS-P1-19). A Sales Manager reassigns within their own team:
	the lead must be one of their team's, and so must the new agent. The Company Admin may pick any agent.
	The lead's open follow ups and future site visits go with it, the change is logged and the new agent
	is told (SOS-P1-23)."""
	result = assignment.reassign([lead], assigned_to, assignment.MANUAL_METHOD, note)
	return {"name": lead, **result}


@sellos_api(COMPANY_ADMIN, SALES_MANAGER)
def bulk_reassign_leads(assigned_to, leads=None, filters=None):
	"""Give many leads to one agent (SOS-P1-19): the `leads` listed, or every lead the list `filters` find
	(the same keys as list_leads). Open follow ups and future site visits go with each lead. A Sales
	Manager may move only their team's leads to an agent of their team. All of it happens, or none."""
	return assignment.bulk_reassign(assigned_to, leads=leads, filters=filters)


@sellos_api(COMPANY_ADMIN, SALES_MANAGER)
def reassign_options():
	"""The agents the user may give leads to (SOS-P1-19)."""
	return {"agents": assignment.assignable_agents()}


@sellos_api(COMPANY_ADMIN)
def list_assignment_rules():
	"""The rules that assign new leads, the default team and the teams to pick from (SOS-P1-19)."""
	return {
		"rules": frappe.get_all(
			assignment.RULE,
			fields=["name", "rule_name", "enabled", "rule_type", "priority", "source", "locality", "team"],
			order_by="priority asc, creation asc",
			limit_page_length=0,
		),
		"default_team": assignment.default_team(),
		"rule_types": list(assignment.RULE_TYPES),
		"teams": frappe.get_all("Sales Team", fields=["name", "team_name"], order_by="team_name asc"),
		"sources": lead_sources.list_sources(),
	}


@sellos_api(COMPANY_ADMIN)
def save_assignment_rule(name=None, values=None):
	"""Add a rule, or change one (SOS-P1-19)."""
	values = _values(values, ("rule_name", "enabled", "rule_type", "priority", "source", "locality", "team"))
	if name:
		doc = frappe.get_doc(assignment.RULE, name)
		doc.check_permission("write")
		doc.update(values)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": assignment.RULE, **values})
		doc.check_permission("create")
		doc.insert()
	return {"name": doc.name}


@sellos_api(COMPANY_ADMIN)
def delete_assignment_rule(name):
	"""Remove a rule. Leads it already assigned stay where they are."""
	frappe.get_doc(assignment.RULE, name).check_permission("delete")
	frappe.delete_doc(assignment.RULE, name)
	return {"deleted": name}


@sellos_api(COMPANY_ADMIN)
def set_default_team(team=None):
	"""The team that takes a new lead no rule matches (SOS-P1-19). Empty clears it."""
	if team and not frappe.db.exists("Sales Team", team):
		frappe.throw(_("That team does not exist."))
	frappe.db.set_single_value("SellOS Settings", "default_team", team or None)
	return {"default_team": team or None}


@sellos_api(*READERS)
def save_lead(name=None, values=None):
	doc = _save("Lead", name, values, LEAD_FIELDS)
	return get_lead(doc.name)


@sellos_api(*READERS)
def get_lead(name):
	"""The lead, its client and a timeline of activities, tasks and visits, newest first."""
	lead = frappe.get_doc("Lead", name)
	lead.check_permission("read")
	return {
		"lead": lead.as_dict(no_nulls=True),
		"requirements": requirements_view(lead),
		"client": client_view(frappe.get_doc("Client", lead.client)),
		"can_merge": COMPANY_ADMIN in frappe.get_roles(),
		"timeline": _timeline(name),
		"assignments": _assignments(lead),
		"follow_up": _next_follow_up(lead),
		"consent": consent.consent_view(name),
		"pipeline": pipeline.stage_view(lead),
		"call_lists": {
			"outcomes": call_outcomes.list_outcomes(),
			"lost_reasons": call_outcomes.list_lost_reasons(),
		},
	}


def _assignments(lead) -> list[dict]:
	"""The lead's assignment log with names, newest first (SOS-P1-19)."""
	rows = assignment.history(lead.name)
	people = {
		u.name: u.full_name
		for u in frappe.get_all("User", filters={"name": ["in", _emails(rows)]}, fields=["name", "full_name"])
	}
	return [
		{**row, "from_name": people.get(row.from_agent), "to_name": people.get(row.to_agent)} for row in rows
	]


def _emails(rows) -> list[str]:
	return list({email for row in rows for email in (row.from_agent, row.to_agent) if email} or [""])


def _next_follow_up(lead) -> dict:
	"""The lead's next open follow up and whether it is untouched (SOS-P1-22)."""
	row = frappe._dict(name=lead.name, stage=lead.stage, archived=lead.archived, creation=lead.creation)
	follow_ups.annotate([row])
	return {key: row[key] for key in FOLLOW_UP_KEYS} | {"untouched_days": follow_ups.untouched_days()}


def _timeline(lead):
	items = []
	for row in frappe.get_list(
		"Lead Activity",
		filters={"lead": lead, "archived": 0},
		fields=["name", "activity_type", "activity_date", "outcome", "duration_seconds", "notes", "owner"],
	):
		items.append({"kind": "activity", "when": row.activity_date, "title": row.activity_type, **row})
	for row in frappe.get_list(
		"Lead Task",
		filters={"lead": lead, "archived": 0},
		fields=["name", "title", "due_date", "due_at", "status", "assigned_to", "notes"],
	):
		items.append(
			{
				"kind": "task",
				"when": row.due_at or row.due_date,
				"overdue": row.status == "Open"
				and follow_ups.due_state(row.due_at, row.due_date) == follow_ups.OVERDUE,
				**row,
			}
		)
	for row in frappe.get_list(
		"Site Visit",
		filters={"lead": lead, "archived": 0},
		fields=[
			"name",
			"project_name",
			"visit_datetime",
			"agent",
			"status",
			"confirmation_status",
			"visit_outcome",
			"notes",
		],
	):
		items.append({"kind": "visit", "when": row.visit_datetime, "title": row.project_name, **row})
	return sorted(items, key=lambda item: str(item["when"]), reverse=True)


@sellos_api(*LOGGERS)
def add_activity(lead, activity_type, notes=None, activity_date=None):
	values = {
		"lead": lead,
		"activity_type": activity_type,
		"notes": notes,
		"activity_date": activity_date or now_datetime(),
	}
	return _save("Lead Activity", None, values, ACTIVITY_FIELDS).as_dict()


@sellos_api(*LOGGERS)
def save_task(name=None, values=None):
	return _save("Lead Task", name, values, TASK_FIELDS).as_dict()


@sellos_api(*LOGGERS)
def complete_follow_up(
	name, outcome=None, notes=None, duration_seconds=None, follow_up_at=None, stage=None, lost_reason=None
):
	"""Mark a follow up done (SOS-P1-22). It needs the call outcome (SOS-P1-21) or a note. An outcome logs
	the call on the lead and, when it needs one, the next follow up at `follow_up_at`."""
	_writable_lead(frappe.db.get_value("Lead Task", name, "lead"))
	return follow_ups.complete(name, outcome, notes, duration_seconds, follow_up_at, stage, lost_reason)


@sellos_api(*LOGGERS)
def list_follow_ups(status="Open", everyone=0):
	"""The follow ups of the signed in user, soonest first, each marked due or overdue (SOS-P1-22).
	`everyone` lists those of every lead the user may see."""
	return follow_ups.list_follow_ups(status=status, everyone=cint(everyone))


@sellos_api(*READERS)
def get_follow_up_settings():
	"""The days after which a lead in an Open stage with no open follow up is untouched (SOS-P1-22)."""
	return {"untouched_days": follow_ups.untouched_days()}


@sellos_api(COMPANY_ADMIN)
def save_follow_up_settings(untouched_days):
	"""A Company Admin sets the number of days for the untouched flag (SOS-P1-22)."""
	return {"untouched_days": follow_ups.set_untouched_days(untouched_days)}


@sellos_api(*READERS)
def get_consent_enforcement():
	"""Whether Consent enforcement is On for this company (SOS-P2-04). Off by default."""
	return {"consent_enforcement": consent.enforcement_on()}


@sellos_api(COMPANY_ADMIN)
def set_consent_enforcement(on):
	"""A Company Admin switches Consent enforcement On or Off (SOS-P2-04). Every change is logged."""
	return {"consent_enforcement": consent.set_enforcement(on)}


@sellos_api(*LOGGERS)
def save_site_visit(name=None, values=None):
	"""Book or change a site visit (SOS-P1-25): the lead, the project, the date and time and the agent
	(the lead's agent unless another is chosen). A new visit moves its lead to Site visit booked unless
	the lead is already further on. Returns the visit with stage_moved and lead_stage."""
	return site_visits.book(_values(values, VISIT_FIELDS), name)


@sellos_api(*LOGGERS)
def site_visit_calendar(view="week", date=None):
	"""The signed in user's site visits for a day or a week, grouped by day (SOS-P1-25). An Agent sees
	their own, a Sales Manager their team's and a Company Admin everyone's."""
	return site_visits.calendar(view, date)


@sellos_api(*LOGGERS)
def tomorrows_site_visits():
	"""Tomorrow's visits with each confirmation status, for the agent to confirm by phone (SOS-P1-25)."""
	return site_visits.tomorrows_visits()


@sellos_api(*LOGGERS)
def confirm_site_visit(name, confirmation_status, visit_datetime=None):
	"""Set a visit's confirmation: Not confirmed, Confirmed, Rescheduled (with the new time) or
	Cancelled (SOS-P1-25)."""
	return site_visits.confirm(name, confirmation_status, visit_datetime)


@sellos_api(*LOGGERS)
def complete_site_visit(name, outcome=None, outcome_notes=None):
	"""Mark a visit Done. The outcome is required, and the next stage it offers is returned, not applied
	(SOS-P1-25). The agent accepts it with move_lead_stage."""
	return site_visits.complete(name, outcome, outcome_notes)


@sellos_api(*LOGGERS)
def site_visit_options():
	"""The agents, outcomes and confirmations the site visit screens offer the user (SOS-P1-25)."""
	return site_visits.options()


@sellos_api(*LOGGERS)
def today_screen():
	"""What the signed in user does today (SOS-P1-26): follow ups due and overdue, new leads, today's site
	visits and tomorrow's to confirm, in time order, with the counts of each. An Agent gets their own, a
	Sales Manager their team's with the counts of each agent, a Company Admin everyone's. Each row has the
	number to call as the role sees it: masked for an Agent and a Sales Manager, in full for a Company
	Admin (the full number shown is logged, P1.06B). Consent is a warning on the row and never blocks."""
	view = today.today_view()
	rows = [row for key in today.SECTIONS for row in view[key]]
	clients = sorted({row.client for row in rows if row.client})
	phones = {}
	for name in clients:
		shown = client_view(frappe.get_doc("Client", name), log=False)
		phones[name] = {"phone": shown["phone"], "overseas_phone": shown["overseas_phone"]}
	for row in rows:
		row.update(phones.get(row.client, {"phone": "", "overseas_phone": ""}))
	if _sees_phone():
		log_full_number_shown(clients)
	view["full_numbers"] = cint(_sees_phone())
	return view


def _writable_lead(lead):
	doc = frappe.get_doc("Lead", lead)
	doc.check_permission("write")
	return doc


@sellos_api(*LOGGERS)
def record_consent(lead, basis, evidence_link=None):
	"""Record a lawful basis for a lead (P1.08). A record with no evidence link is refused. The time
	is now, and the expiry is set from the basis. Recording again for the same basis renews it."""
	_writable_lead(lead)
	doc = frappe.get_doc(
		{"doctype": "Consent Record", "lead": lead, "basis": basis, "evidence_link": evidence_link}
	)
	doc.check_permission("create")
	doc.flags.ignore_permissions = True
	doc.insert()
	return consent.consent_view(lead)


@sellos_api(*LOGGERS)
def record_opt_out(lead, source):
	"""An explicit stop request: Opted out, with its time and source. It blocks nothing (P1.08)."""
	_writable_lead(lead)
	consent.record_opt_out(lead, source)
	return consent.consent_view(lead)


@sellos_api(*LOGGERS)
def record_dnd_result(lead, registered=1):
	"""A do not call result is known for the lead's number. Registered shows an amber warning."""
	_writable_lead(lead)
	consent.record_dnd_result(lead, cint(registered))
	return consent.consent_view(lead)


@sellos_api(COMPANY_ADMIN)
def preview_lead_import(csv_text, mapping=None):
	"""What importing a bought list would do, with nothing written (SOS-P1-12): the column mapping (the
	one given, or guessed from the headers), the counts of new, merged and skipped rows, and the first
	rows with their numbers masked."""
	return lead_import.preview(csv_text, mapping)


@sellos_api(COMPANY_ADMIN)
def import_bought_list(csv_text, mapping=None, list_name=None):
	"""Import a bought lead list (SOS-P1-12). Every lead gets the source Bought list and the consent status
	Unknown, or Registered DND when the file carries a known do not call result. Duplicates are merged.
	Nothing the import sets stops a call, an SMS or a WhatsApp message (consent never blocks)."""
	return lead_import.import_list(csv_text, mapping, list_name)


@sellos_api(*READERS)
def set_archived(doctype, name, archived=1):
	"""Archive or restore a record. This is the only way to remove one from view."""
	if doctype not in ARCHIVABLE:
		frappe.throw(_("{0} cannot be archived.").format(doctype), frappe.PermissionError)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	doc.archived = cint(archived)
	doc.archived_on = None
	doc.flags.ignore_permissions = True
	doc.save()
	return {"name": doc.name, "archived": doc.archived}


@sellos_api(*READERS)
def list_notifications():
	"""The signed in user's unread notifications, newest first, with the unread count (SOS-P1-23)."""
	return notifications.unread_for()


@sellos_api(*READERS)
def mark_notification_read(name):
	"""Mark one of the user's own notifications read. Another user's is reported as not found."""
	return notifications.mark_read(name)


@sellos_api(*READERS)
def mark_all_notifications_read():
	"""Mark every notification of the signed in user read."""
	return notifications.mark_all_read()
