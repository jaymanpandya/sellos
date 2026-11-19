# SOS-P1-19 one row of the assignment log: which lead went from whom to whom, how, and who did it.
import frappe
from frappe import _
from frappe.model.document import Document


class LeadAssignment(Document):
	def on_trash(self):
		frappe.throw(_("The assignment log is never deleted."), frappe.PermissionError)
