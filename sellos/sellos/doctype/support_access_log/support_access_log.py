# P1.13 one line per support action: who, when, and what. Written by sellos.access.support only.
import frappe
from frappe import _
from frappe.model.document import Document


class SupportAccessLog(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("The support access log can not be changed."), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("The support access log is kept, never deleted."), frappe.PermissionError)
