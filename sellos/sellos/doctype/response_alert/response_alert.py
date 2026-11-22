# SOS-P7-13 one missed response limit of one lead, kept once for SOS-P5-02's reports.
import frappe
from frappe import _
from frappe.model.document import Document


class ResponseAlert(Document):
	def on_trash(self):
		frappe.throw(_("A missed response is never deleted."), frappe.PermissionError)
