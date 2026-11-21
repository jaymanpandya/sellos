"""Developers, projects, units and properties in the web app (SOS-P4-01).

A Company Admin or an Agent records and edits inventory; a Sales Manager reads it. A Client, a Channel
Partner and the Platform Admin see none (a partner is shown shared inventory by SOS-P7-03). Every record
is saved through its DocType, so its checks and the DocType permissions run on every call. Nothing is
deleted: a record is archived. A unit's or property's status changes only through `set_inventory_status`,
which logs who changed it and when.
"""

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.inventory.base import STATUSES

READERS = (COMPANY_ADMIN, AGENT, SALES_MANAGER)
EDITORS = (COMPANY_ADMIN, AGENT)

# What a caller may set on each record. The status, the archive flag and the log are never in these lists.
FIELDS = {
	"Developer": ("developer_name", "rera_registration", "contact_person", "email", "website", "notes"),
	"Project": ("project_name", "developer", "rera_number", "project_status", "city", "locality", "address"),
	"Unit": ("project", "unit_number", "configuration", "carpet_area", "floor", "parking"),
	"Property": (
		"title",
		"property_type",
		"building_name",
		"rera_number",
		"configuration",
		"carpet_area",
		"floor",
		"parking",
		"city",
		"locality",
		"address",
	),
}
# A field that is set when a record is made and never changed.
FIXED_AFTER_CREATE = {"Developer": ("developer_name",), "Unit": ("project",)}
STATUS_KINDS = ("Unit", "Property")
ARCHIVABLE = ("Developer", "Project", "Unit", "Property")

LIST_FIELDS = {
	"Developer": ["name", "developer_name", "rera_registration", "contact_person", "email", "archived"],
	"Project": [
		"name",
		"project_name",
		"developer",
		"rera_number",
		"project_status",
		"city",
		"locality",
		"address",
		"archived",
	],
	"Unit": [
		"name",
		"project",
		"unit_number",
		"configuration",
		"carpet_area",
		"floor",
		"parking",
		"status",
		"archived",
	],
	"Property": [
		"name",
		"title",
		"property_type",
		"building_name",
		"rera_number",
		"configuration",
		"carpet_area",
		"floor",
		"parking",
		"city",
		"locality",
		"status",
		"archived",
	],
}


def _values(values) -> dict:
	return frappe.parse_json(values) if isinstance(values, str) else (values or {})


def _flag(value) -> bool:
	return str(value).lower() in ("1", "true", "yes")


def _rows(doctype, include_archived=False, filters=None) -> list[dict]:
	filters = dict(filters or {})
	if not include_archived:
		filters["archived"] = 0
	return frappe.get_list(doctype, fields=LIST_FIELDS[doctype], filters=filters, order_by="creation asc")


def _log(doc) -> list[dict]:
	people = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	return [
		{
			"changed_on": row.changed_on,
			"changed_by": row.changed_by,
			"changed_by_name": people.get(row.changed_by, row.changed_by),
			"from_status": row.from_status or "",
			"to_status": row.to_status,
			"reason": row.reason or "",
		}
		for row in doc.status_log
	]


def _with_log(doctype, rows) -> list[dict]:
	"""Each row with its status log, for the units and properties."""
	out = []
	for row in rows:
		doc = frappe.get_doc(doctype, row["name"])
		out.append({**row, "log": _log(doc)})
	return out


def _unit_counts(project) -> dict:
	counts = {status: 0 for status in STATUSES}
	for status in frappe.get_list("Unit", filters={"project": project, "archived": 0}, pluck="status"):
		counts[status] += 1
	counts["total"] = sum(counts.values())
	return counts


def _overview() -> dict:
	projects = _rows("Project")
	for row in projects:
		row["units"] = _unit_counts(row["name"])
	return {
		"developers": _rows("Developer"),
		"projects": projects,
		"properties": _with_log("Property", _rows("Property")),
		"can_edit": any(role in frappe.get_roles() for role in EDITORS),
		"statuses": list(STATUSES),
		"configurations": [
			c for c in frappe.get_meta("Unit").get_field("configuration").options.split("\n") if c
		],
		"property_types": frappe.get_meta("Property").get_field("property_type").options.split("\n"),
		"project_statuses": frappe.get_meta("Project").get_field("project_status").options.split("\n"),
	}


@sellos_api(*READERS)
def inventory_overview():
	"""Developers, projects (with how many units are in each status) and properties, archived ones left out."""
	return _overview()


@sellos_api(*READERS)
def get_project(name):
	"""One project with its units, each with its status log."""
	if not name or not frappe.db.exists("Project", name):
		frappe.throw(_("There is no project {0}.").format(name), frappe.DoesNotExistError)
	project = frappe.get_doc("Project", name)
	project.check_permission("read")
	row = {key: project.get(key) for key in LIST_FIELDS["Project"]}
	return {
		"project": {**row, "units": _unit_counts(name)},
		"units": _with_log("Unit", _rows("Unit", filters={"project": name})),
		"can_edit": any(role in frappe.get_roles() for role in EDITORS),
		"statuses": list(STATUSES),
		"configurations": [
			c for c in frappe.get_meta("Unit").get_field("configuration").options.split("\n") if c
		],
	}


def _save(doctype, name, values):
	values = _values(values)
	allowed = FIELDS[doctype]
	if name:
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("write")
		fixed = FIXED_AFTER_CREATE.get(doctype, ())
		for field in allowed:
			if field in values and field not in fixed:
				doc.set(field, values[field])
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": doctype, **{k: values[k] for k in allowed if k in values}})
		doc.insert()
	return doc


@sellos_api(*EDITORS)
def save_developer(values, name=None):
	"""Make a developer, or correct one (its name is fixed once made)."""
	doc = _save("Developer", name, values)
	return {"name": doc.name, **_overview()}


@sellos_api(*EDITORS)
def save_project(values, name=None):
	"""Make a project, or correct one. The RERA number is required."""
	doc = _save("Project", name, values)
	return {"name": doc.name, **_overview()}


@sellos_api(*EDITORS)
def save_unit(values, name=None):
	"""Make a unit of a project (Available), or correct one. The project of a unit is fixed once made."""
	doc = _save("Unit", name, values)
	return {"name": doc.name, **get_project(doc.project)}


@sellos_api(*EDITORS)
def save_property(values, name=None):
	"""Make a secondary property (Available), or correct one."""
	doc = _save("Property", name, values)
	return {"name": doc.name, **_overview()}


@sellos_api(*EDITORS)
def set_inventory_status(doctype, name, status, reason=""):
	"""Move a unit or property to Available, Held or Sold. The change is logged with who made it and when."""
	if doctype not in STATUS_KINDS:
		frappe.throw(_("Only a unit or a property has a status."))
	if status not in STATUSES:
		frappe.throw(_("The status must be one of {0}.").format(", ".join(STATUSES)))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	if doc.archived:
		frappe.throw(_("An archived record can not change status. Restore it first."))
	if doc.status == status:
		frappe.throw(_("It is already {0}.").format(status))
	doc.status = status
	doc.flags.status_reason = reason
	doc.save()
	return {"name": doc.name, **(get_project(doc.project) if doctype == "Unit" else _overview())}


@sellos_api(COMPANY_ADMIN)
def set_inventory_archived(doctype, name, archived=1):
	"""Archive a record, or restore it. Nothing is deleted."""
	if doctype not in ARCHIVABLE:
		frappe.throw(_("{0} can not be archived here.").format(doctype))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	doc.archived = 1 if _flag(archived) else 0
	doc.save()
	return {"name": doc.name, **_overview()}
