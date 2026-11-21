# SOS-P7-02 a buyer a channel partner registered, and the protection window that decides who is owed commission.
import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime

from sellos.crm.base import ArchiveOnly, stamp_archive

REGISTERED = "Registered"
APPROVED = "Approved"
VISITED = "Visited"
BOOKED = "Booked"
EXPIRED = "Expired"
REJECTED = "Rejected"
STATUSES = (REGISTERED, APPROVED, VISITED, BOOKED, EXPIRED, REJECTED)
# The statuses in which the registration may still be protected (see is_protected in the access module).
LIVE = (APPROVED, VISITED)

MOVES = {
	(REGISTERED, APPROVED),
	(REGISTERED, REJECTED),
	(APPROVED, VISITED),
	(APPROVED, BOOKED),
	(VISITED, BOOKED),
	(APPROVED, EXPIRED),
	(VISITED, EXPIRED),
}


class PartnerRegistration(ArchiveOnly):
	def before_insert(self):
		self.status = REGISTERED
		self.registered_on = self.registered_on or now_datetime()
		self.append(
			"status_log",
			{
				"changed_on": self.registered_on,
				"changed_by": frappe.session.user,
				"from_status": "",
				"to_status": REGISTERED,
			},
		)

	def validate(self):
		stamp_archive(self)
		if not self.is_new() and self.has_value_changed("status") and not self.flags.via_transition:
			frappe.throw(
				_("A registration's status changes only by approving, rejecting or following the lead."),
				frappe.PermissionError,
			)

	def change_status(self, to, note="", on=None):
		"""Move the registration and log who did it and when. Only sellos.access.partner_registrations
		calls this, after it has checked the role. `on` is the clock the move is stamped with."""
		on = on or now_datetime()
		note = (note or "").strip()
		if (self.status, to) not in MOVES:
			frappe.throw(_("A registration that is {0} can not become {1}.").format(self.status, to))
		if to == REJECTED and not note:
			frappe.throw(_("Give a reason for the rejection."))
		self.append(
			"status_log",
			{
				"changed_on": on,
				"changed_by": frappe.session.user,
				"from_status": self.status,
				"to_status": to,
				"note": note,
			},
		)
		self.status = to
		if to == APPROVED:
			self.approved_on = on
			self.decided_by = frappe.session.user
			self.protected_until = add_days(on, protection_days())
		elif to == REJECTED:
			self.decided_by = frappe.session.user
			self.rejection_reason = note
		self.flags.via_transition = True
		self.flags.ignore_permissions = True
		self.save()

	def log_note(self, note):
		"""A line in the log that is not a status move (the lead's partner was changed)."""
		self.append(
			"status_log",
			{
				"changed_on": now_datetime(),
				"changed_by": frappe.session.user,
				"from_status": self.status,
				"to_status": self.status,
				"note": note,
			},
		)
		self.flags.via_transition = True
		self.flags.ignore_permissions = True
		self.save()


def raw_setting(field):
	"""A SellOS Settings value as saved, or None when it was never saved. (get_single_value answers 0 for an
	Int that was never saved, which is not the company's choice, so the defaults need this.)"""
	table = frappe.qb.DocType("Singles")
	rows = (
		frappe.qb.from_(table)
		.select(table.value)
		.where((table.doctype == "SellOS Settings") & (table.field == field))
		.run()
	)
	# A saved settings form stores 0 for an Int nobody filled in, and the save method refuses anything
	# below 1, so 0 here also means "never set".
	return rows[0][0] if rows and rows[0][0] not in (None, "", "0", 0) else None


def protection_days() -> int:
	value = raw_setting("partner_protection_days")
	return 90 if value is None else max(cint(value), 0)
