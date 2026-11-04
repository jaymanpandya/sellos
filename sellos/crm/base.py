"""Shared rules for the CRM records (P1.06).

* Nothing is deleted. A record is archived, and every delete is refused, for every role.
* Phone numbers are stored in full, readable only at permission level 1 (Company Admin). The
  masked copy is what everyone else sees.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today


class ArchiveOnly(Document):
	def on_trash(self):
		frappe.throw(
			_("{0} records are archived, never deleted.").format(self.doctype), frappe.PermissionError
		)


def mask_phone(value: str | None) -> str:
	"""Keep the last three digits: '+91 98200 12345' -> '*********345'."""
	digits = "".join(ch for ch in (value or "") if ch.isdigit())
	if not digits:
		return ""
	return "*" * max(len(digits) - 3, 4) + digits[-3:]


def is_overdue(due_date, status, on=None) -> bool:
	"""A task is overdue when it is not done and its due date is before today."""
	if not due_date or status == "Done":
		return False
	return getdate(due_date) < getdate(on or today())


def stamp_archive(doc):
	"""Fill or clear the archive details when the archived flag changes."""
	if doc.archived and not doc.archived_on:
		doc.archived_on = now_datetime()
		doc.archived_by = frappe.session.user
	elif not doc.archived:
		doc.archived_on = None
		doc.archived_by = None
