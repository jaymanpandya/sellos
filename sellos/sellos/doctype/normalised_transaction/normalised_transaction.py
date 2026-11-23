# SOS-P3-03 one raw transaction cleaned: English text, standard date, rupees and carpet square feet.
# Lives on the control site only. Written by sellos.intel.normalise_store, never by hand.
import frappe
from frappe import _
from frappe.model.document import Document


class NormalisedTransaction(Document):
	def on_trash(self):
		frappe.throw(_("A normalised record is never deleted."))
