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
from sellos.crm.base import is_overdue

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
LEAD_FIELDS = ("client", "source", "assigned_to", "notes")
ACTIVITY_FIELDS = ("lead", "activity_type", "activity_date", "notes")
TASK_FIELDS = ("lead", "title", "due_date", "status", "assigned_to", "notes")
VISIT_FIELDS = ("lead", "project_name", "visit_datetime", "status", "notes")
ARCHIVABLE = ("Client", "Lead", "Lead Activity", "Lead Task", "Site Visit")


def _values(values, allowed):
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	return {key: values[key] for key in allowed if key in values}


def _sees_phone() -> bool:
	return COMPANY_ADMIN in frappe.get_roles() or "System Manager" in frappe.get_roles()


def _save(doctype, name, values, allowed):
	"""Create or update with the user's own permission checked, then write the allowed fields."""
	values = _values(values, allowed)
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


def client_view(doc) -> dict:
	"""A client as the current user may see it. Only a Company Admin gets the full phone numbers."""
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
	return [client_view(frappe.get_doc("Client", name)) for name in names]


@sellos_api(*READERS)
def save_client(name=None, values=None):
	return client_view(_save("Client", name, values, CLIENT_FIELDS))


@sellos_api(*READERS)
def list_leads(search=None, include_archived=0):
	filters = {} if cint(include_archived) else {"archived": 0}
	leads = frappe.get_list(
		"Lead",
		filters=filters,
		or_filters=_search(search, ("lead_title", "source")),
		fields=["name", "lead_title", "client", "source", "assigned_to", "archived", "modified"],
		order_by="modified desc",
		limit_page_length=100,
	)
	for lead in leads:
		lead["client_name"] = frappe.db.get_value("Client", lead.client, "client_name")
		tasks = frappe.get_all(
			"Lead Task", filters={"lead": lead.name, "archived": 0, "status": "Open"}, fields=["due_date"]
		)
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
		"client": client_view(frappe.get_doc("Client", lead.client)),
		"timeline": _timeline(name),
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
