# SOS-P1-09 a per company key for a public or keyed endpoint. Only a hash of the key is kept, and an API
# never returns it. Nothing is deleted: a key is switched off.
import frappe
from frappe import _
from frappe.model.document import Document


class IntakeKey(Document):
	def on_trash(self):
		frappe.throw(_("A key is switched off, never deleted."))
