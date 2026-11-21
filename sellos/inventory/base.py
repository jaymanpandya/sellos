"""Shared rules for the inventory records: Developer, Project, Unit and Property (SOS-P4-01).

* Nothing is deleted. A record is archived, and every delete is refused, for every role.
* A unit or property is Available, Held or Sold. SOS-P7-06 adds Booked and Blocked. Every change of
  status is logged with who made it and when, whichever way the record is saved.
* A RERA number is kept in capitals with no spaces, so the same number is never stored two ways.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

AVAILABLE = "Available"
HELD = "Held"
SOLD = "Sold"
STATUSES = (AVAILABLE, HELD, SOLD)

# Printed RERA numbers differ by state (P51800012345, PRM/KA/RERA/1251/309/PR/190101/000123, UPRERAPRJ12345,
# RC/REP/HARERA/GGM/123/456/2019/12), so the check only refuses what can not be one: it must start with a
# letter or digit, use only letters, digits, / and -, and be 5 to 40 characters long.
_RERA = re.compile(r"^[A-Z0-9][A-Z0-9/-]{4,39}$")


def clean_rera_number(value, required=False) -> str:
	"""The RERA number in capitals with no spaces, or "" when blank and not required."""
	value = re.sub(r"\s+", "", str(value or "")).upper()
	if not value:
		if required:
			frappe.throw(_("Enter the RERA number."))
		return ""
	if not _RERA.match(value):
		frappe.throw(_("Enter the RERA number as it is printed, for example P51800012345."))
	return value


def squash(value) -> str:
	return " ".join(str(value or "").split())


class InventoryRecord(Document):
	"""A record that is archived and never deleted."""

	def on_trash(self):
		frappe.throw(
			_("{0} records are archived, never deleted.").format(self.doctype), frappe.PermissionError
		)

	def stamp_archive(self):
		if self.archived and not self.archived_on:
			self.archived_on = now_datetime()
			self.archived_by = frappe.session.user
		elif not self.archived:
			self.archived_on = None
			self.archived_by = None


class StatusLogged(InventoryRecord):
	"""A unit or a property: a status that moves between Available, Held and Sold, and a log of the moves."""

	def validate(self):
		self.stamp_archive()
		self.validate_record()
		self.log_status()

	def validate_record(self):
		"""The record's own checks. The subclass replaces this."""

	def check_measures(self):
		# The web app sends numbers as the text typed in the box.
		self.carpet_area = flt(self.carpet_area)
		self.parking = cint(self.parking)
		if self.floor not in (None, ""):
			self.floor = cint(self.floor)
		if self.carpet_area <= 0:
			frappe.throw(_("Enter the carpet area in square feet, more than zero."))
		if self.parking < 0:
			frappe.throw(_("Parking slots can not be below zero."))

	def log_status(self):
		"""Log a new record's first status, and every later change of status."""
		if not self.status:
			self.status = AVAILABLE
		if self.status not in STATUSES:
			frappe.throw(_("The status must be one of {0}.").format(", ".join(STATUSES)))
		old = None if self.is_new() else self.get_doc_before_save().status
		if old == self.status and not self.is_new():
			return
		self.append(
			"status_log",
			{
				"changed_on": now_datetime(),
				"changed_by": frappe.session.user,
				"from_status": old or "",
				"to_status": self.status,
				"reason": (self.flags.status_reason or "").strip(),
			},
		)
