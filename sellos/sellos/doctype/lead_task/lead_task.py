# P1.06 a to do with a due date.
import frappe

from sellos.crm.base import ArchiveOnly, stamp_archive


class LeadTask(ArchiveOnly):
	def validate(self):
		if not self.assigned_to:
			self.assigned_to = frappe.db.get_value("Lead", self.lead, "assigned_to")
		stamp_archive(self)
