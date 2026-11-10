"""A record's change history shows only the fields its reader may see (P1.06B).

Opening a record through the API (getdoc, get_docinfo) also sends its latest changes, each changed
field with its old and new value. The record comes without the fields the reader's roles can't
read (permission level 1 holds the full phone numbers), but its history came with them. These
wrap both methods through `override_whitelisted_methods` and take those fields out of the history.
Everyone who may read the fields sees it unchanged. The approach follows BuildOS's
buildos.security.field_history (BOS-282)."""

import json

import frappe
from frappe.desk.form import load

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, CHANNEL_PARTNER, CLIENT, COMPANY_ADMIN, PLATFORM_ADMIN

# Every role that opens records through these two methods.
OPENERS = (PLATFORM_ADMIN, COMPANY_ADMIN, AGENT, CLIENT, CHANNEL_PARTNER)


@sellos_api(*OPENERS)
def getdoc(doctype: str, name: str | int):
	load.getdoc(doctype, name)
	hide_unreadable_changes()


@sellos_api(*OPENERS)
def get_docinfo(doc=None, doctype: str | None = None, name: str | int | None = None):
	load.get_docinfo(doc, doctype, name)
	hide_unreadable_changes()


def hide_unreadable_changes():
	docinfo = frappe.response.get("docinfo")
	if not docinfo or not docinfo.get("versions"):
		return
	hidden = unreadable_fields(docinfo.get("doctype"))
	if not hidden:
		return
	for version in docinfo.versions:
		version["data"] = without_fields(version.get("data"), hidden)


def unreadable_fields(doctype: str, parenttype: str | None = None) -> set[str]:
	"""The fields of `doctype` the user's roles can't read. For a table, under its parent's permissions."""
	meta = frappe.get_meta(doctype)
	levels = meta.get_permlevel_access("read", parenttype)
	hidden = {df.fieldname for df in meta.get_high_permlevel_fields() if df.permlevel not in levels}
	if parenttype is None:
		for df in meta.get_table_fields():
			hidden.update(f"{df.fieldname}.{field}" for field in unreadable_fields(df.options, doctype))
	return hidden


def without_fields(data, hidden: set[str]):
	"""A Version's data with the changes to `hidden` fields taken out. Table fields are `<table>.<field>`."""
	try:
		diff = json.loads(data) if isinstance(data, str) else data
	except ValueError:
		return data
	if not isinstance(diff, dict):
		return data

	diff["changed"] = [row for row in diff.get("changed") or [] if row[0] not in hidden]
	for key in ("added", "removed"):
		for table, row in diff.get(key) or []:
			for field in list(row or {}):
				if f"{table}.{field}" in hidden:
					row.pop(field)
	for entry in diff.get("row_changed") or []:
		table, changes = entry[0], entry[3]
		entry[3] = [change for change in changes if f"{table}.{change[0]}" not in hidden]
	return frappe.as_json(diff, indent=None, separators=(",", ":"))
