# SOS-LOOP a note on a lead, a seller or a mandate. Its type, label and attachments are checked by
# sellos.crm.notes, which every call goes through. A note is removed (hidden), never deleted.
import frappe
from frappe import _
from frappe.model.document import Document


class RecordNote(Document):
	def validate(self):
		if self.mandate and frappe.db.get_value("Mandate", self.mandate, "lead") != self.lead:
			frappe.throw(_("The mandate belongs to another lead."))
		if not self.body and not self.attachments and not self.flags.attachments_pending:
			frappe.throw(_("Write the note or attach a file."))

	def on_trash(self):
		frappe.throw(_("Notes are removed from view, never deleted."), frappe.PermissionError)
