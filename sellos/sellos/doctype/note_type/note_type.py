# SOS-LOOP a type of note, from the company's managed list. A type is renamed or hidden, never deleted.
import frappe
from frappe import _
from frappe.model.document import Document


class NoteType(Document):
	def on_trash(self):
		frappe.throw(_("A note type is hidden, never deleted."), frappe.PermissionError)
