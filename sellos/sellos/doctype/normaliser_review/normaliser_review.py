# SOS-P3-03 a raw transaction the normaliser could not read, waiting for a person.
# Lives on the control site only. It is Resolved when a later run reads the record.
import frappe
from frappe import _
from frappe.model.document import Document


class NormaliserReview(Document):
	def on_trash(self):
		frappe.throw(_("A review entry is never deleted."))
