"""Listings in the web app (SOS-P4-02).

A listing offers a unit or a property as Primary, Direct or Partner, and the website shows it only once it is
published. A Company Admin or an Agent makes, corrects, publishes and withdraws listings; a Sales Manager reads
them. Every call saves through the Listing DocType, so its checks (a published listing needs its required fields)
and the DocType permissions run on every call, and every change lands in the listing's change history. Nothing
is deleted: a listing is archived.
"""

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.inventory.base import AVAILABLE, HELD
from sellos.sellos.doctype.listing.listing import LISTING_TYPES

READERS = (COMPANY_ADMIN, AGENT, SALES_MANAGER)
EDITORS = (COMPANY_ADMIN, AGENT)

# What a caller may set. The publish flag, its stamps, the history and the archive flag are never in this list.
FIELDS = ("title", "listing_type", "unit", "property", "asking_price", "description")


def _values(values) -> dict:
	return frappe.parse_json(values) if isinstance(values, str) else (values or {})


def _flag(value) -> bool:
	return str(value).lower() in ("1", "true", "yes")


def _people() -> dict:
	return {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}


def _row(doc, people) -> dict:
	target = doc.unit or doc.property
	label = ""
	if doc.unit:
		unit = frappe.db.get_value("Unit", doc.unit, ["unit_number", "project"], as_dict=True)
		label = f"{frappe.db.get_value('Project', unit.project, 'project_name')}, unit {unit.unit_number}"
	elif doc.property:
		label = frappe.db.get_value("Property", doc.property, "title")
	return {
		"name": doc.name,
		"title": doc.title,
		"listing_type": doc.listing_type,
		"unit": doc.unit or "",
		"property": doc.property or "",
		"target": target or "",
		"target_label": label,
		"asking_price": doc.asking_price or 0,
		"description": doc.description or "",
		"published": int(doc.published or 0),
		"published_on": str(doc.published_on or ""),
		"published_by_name": people.get(doc.published_by, doc.published_by or ""),
		"archived": int(doc.archived or 0),
		"missing": doc.missing_for_publish(),
		"changes": [
			{
				"changed_on": str(c.changed_on),
				"changed_by_name": people.get(c.changed_by, c.changed_by),
				"what": c.field_label,
				"old": c.old_value or "",
				"new": c.new_value or "",
			}
			for c in doc.changes
		],
	}


def _offerable(doctype) -> list[dict]:
	"""Units and properties that can be offered: not archived, Available or Held."""
	filters = {"archived": 0, "status": ["in", [AVAILABLE, HELD]]}
	if doctype == "Unit":
		rows = frappe.get_list("Unit", fields=["name", "unit_number", "project"], filters=filters)
		names = {p.name: p.project_name for p in frappe.get_all("Project", fields=["name", "project_name"])}
		return [
			{"value": r.name, "label": f"{names.get(r.project, r.project)}, unit {r.unit_number}"}
			for r in rows
		]
	rows = frappe.get_list("Property", fields=["name", "title"], filters=filters)
	return [{"value": r.name, "label": r.title} for r in rows]


def _overview(include_archived=False) -> dict:
	filters = {} if include_archived else {"archived": 0}
	people = _people()
	names = frappe.get_list("Listing", filters=filters, pluck="name", order_by="creation desc")
	return {
		"listings": [_row(frappe.get_doc("Listing", n), people) for n in names],
		"can_edit": any(role in frappe.get_roles() for role in EDITORS),
		"can_archive": COMPANY_ADMIN in frappe.get_roles(),
		"listing_types": list(LISTING_TYPES),
		"units": _offerable("Unit"),
		"properties": _offerable("Property"),
	}


@sellos_api(*READERS)
def listing_overview(include_archived=0):
	"""Listings with their change history, and the units and properties that can be offered."""
	return _overview(_flag(include_archived))


@sellos_api(*EDITORS)
def save_listing(values, name=None):
	"""Make a listing (a draft, never published by this call), or correct one."""
	values = _values(values)
	if name:
		doc = frappe.get_doc("Listing", name)
		doc.check_permission("write")
		for field in FIELDS:
			if field in values:
				value = values[field]
				doc.set(field, (value or None) if field in ("unit", "property") else value)
		doc.save()
	else:
		data = {k: values[k] for k in FIELDS if k in values}
		for key in ("unit", "property"):
			data[key] = data.get(key) or None
		doc = frappe.get_doc({"doctype": "Listing", **data, "published": 0})
		doc.insert()
	return {"name": doc.name, **_overview()}


def _set_published(name, published) -> dict:
	doc = frappe.get_doc("Listing", name)
	doc.check_permission("write")
	if doc.archived:
		frappe.throw(_("An archived listing can not be published. Restore it first."))
	if int(doc.published or 0) != published:
		doc.published = published
		doc.save()
	return {"name": doc.name, **_overview()}


@sellos_api(*EDITORS)
def publish_listing(name):
	"""Publish a listing. It is refused, naming what is missing, unless it has a title, a type, a unit or a
	property, an asking price and a description, and what it offers is Available or Held."""
	return _set_published(name, 1)


@sellos_api(*EDITORS)
def unpublish_listing(name):
	"""Take a listing off the website. It stays, as a draft."""
	return _set_published(name, 0)


@sellos_api(COMPANY_ADMIN)
def set_listing_archived(name, archived=1):
	"""Archive a listing (which also unpublishes it), or restore it. Nothing is deleted."""
	doc = frappe.get_doc("Listing", name)
	doc.check_permission("write")
	doc.archived = 1 if _flag(archived) else 0
	doc.save()
	return {"name": doc.name, **_overview()}
