# SOS-P7-04 the log of a partner's commission statement exported by a Company Admin: who, when, which firm and
# dates, and how many rows. It is written by the export and never changed or deleted.
import frappe
from frappe import _
from frappe.model.document import Document


class CommissionStatementExport(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("An export log is never changed."), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("An export log is never deleted."), frappe.PermissionError)
