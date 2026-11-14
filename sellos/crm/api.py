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
from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN
from sellos.crm import consent
from sellos.crm.base import is_overdue
from sellos.crm.requirements import REQUIREMENT_FIELDS, has_filters, join_values, matches, requirements_view

READERS = (AGENT, CHANNEL_PARTNER, COMPANY_ADMIN)
LOGGERS = (AGENT, COMPANY_ADMIN)  # may log activities, tasks and visits. A partner only reads them.

CLIENT_FIELDS = (
	"client_name",
	"client_type",
	"email",
	"city",
	"country_of_residence",
	"phone",
	"overseas_phone",
)
LEAD_FIELDS = ("client", "source", "assigned_to", "notes", *REQUIREMENT_FIELDS)
ACTIVITY_FIELDS = ("lead", "activity_type", "activity_date", "notes")
TASK_FIELDS = ("lead", "title", "due_date", "status", "assigned_to", "notes")
VISIT_FIELDS = ("lead", "project_name", "visit_datetime", "status", "notes")
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
):
	"""The leads the user may see. The requirement filters (SOS-P1-15) are budget range, configuration
	(one or several), locality and timeline; see sellos.crm.requirements.matches."""
	filters = {} if cint(include_archived) else {"archived": 0}
	if isinstance(configuration, str) and configuration.startswith("["):
		configuration = frappe.parse_json(configuration)
	requirement_filters = {
		"budget_min": budget_min,
		"budget_max": budget_max,
		"configuration": configuration,
		"locality": locality,
		"timeline": timeline,
	}
	narrowed = has_filters(**requirement_filters)
	leads = frappe.get_list(
		"Lead",
		filters=filters,
		or_filters=_search(search, ("lead_title", "source")),
		fields=[
			"name",
			"lead_title",
			"client",
			"source",
			"assigned_to",
			"archived",
			"modified",
			*REQUIREMENT_FIELDS,
		],
		order_by="modified desc",
		limit_page_length=0 if narrowed else 100,
	)
	if narrowed:
		leads = [lead for lead in leads if matches(lead, **requirement_filters)][:100]
	for lead in leads:
		lead["client_name"] = frappe.db.get_value("Client", lead.client, "client_name")
		tasks = frappe.get_all(
			"Lead Task", filters={"lead": lead.name, "archived": 0, "status": "Open"}, fields=["due_date"]
		)
		lead["consent_status"] = consent.compute_status(lead.name)
		lead["consent_warning"] = consent.WARNINGS[lead["consent_status"]][0]
		lead["requirements"] = requirements_view(lead)
		lead["open_tasks"] = len(tasks)
		lead["overdue_tasks"] = sum(is_overdue(t.due_date, "Open") for t in tasks)
	return leads


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
		"timeline": _timeline(name),
		"consent": consent.consent_view(name),
	}


def _timeline(lead):
	items = []
	for row in frappe.get_list(
		"Lead Activity",
		filters={"lead": lead, "archived": 0},
		fields=["name", "activity_type", "activity_date", "notes", "owner"],
	):
		items.append({"kind": "activity", "when": row.activity_date, "title": row.activity_type, **row})
	for row in frappe.get_list(
		"Lead Task",
		filters={"lead": lead, "archived": 0},
		fields=["name", "title", "due_date", "status", "assigned_to", "notes"],
	):
		items.append(
			{"kind": "task", "when": row.due_date, "overdue": is_overdue(row.due_date, row.status), **row}
		)
	for row in frappe.get_list(
		"Site Visit",
		filters={"lead": lead, "archived": 0},
		fields=["name", "project_name", "visit_datetime", "status", "notes"],
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
def save_site_visit(name=None, values=None):
	return _save("Site Visit", name, values, VISIT_FIELDS).as_dict()


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
