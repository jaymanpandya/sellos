# P1.06 a to do with a due date.
import frappe
from frappe.utils import get_datetime

from sellos.crm.base import ArchiveOnly, stamp_archive


class LeadTask(ArchiveOnly):
	def validate(self):
		if self.due_at:  # SOS-P1-21: a follow up has a date and a time. The due date is its day.
			self.due_date = get_datetime(self.due_at).date()
		if not self.assigned_to:
			self.assigned_to = frappe.db.get_value("Lead", self.lead, "assigned_to")
		stamp_archive(self)
