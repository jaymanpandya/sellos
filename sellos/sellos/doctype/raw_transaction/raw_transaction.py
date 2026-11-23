# SOS-P3-02 one registration record exactly as received, with its source, fetch time and hash.
# Lives on the control site only. It is written once and never changed or deleted.
import frappe
from frappe import _
from frappe.model.document import Document


class RawTransaction(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("A raw record is never changed."))

	def on_trash(self):
		frappe.throw(_("A raw record is never deleted."))
