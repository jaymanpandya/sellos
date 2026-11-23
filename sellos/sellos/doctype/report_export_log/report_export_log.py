# SOS-P5-04 the log of a report result that left the screen as a file or an email: the report, whose data it
# held, the dates, the rows and how it went out. Written by the export, never changed or deleted.
import frappe
from frappe import _
from frappe.model.document import Document


class ReportExportLog(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("An export log is never changed."), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("An export log is never deleted."), frappe.PermissionError)
