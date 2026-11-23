# SOS-P3-12 one view of party names. The log holds who, when and which record, never a name. It is written
# once, never changed and never deleted.
import frappe
from frappe import _
from frappe.model.document import Document


class PartyNameAccessLog(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("The access log is never changed."))

	def on_trash(self):
		frappe.throw(_("The access log is never deleted."))
