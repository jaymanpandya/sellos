# SOS-P3-01 one run of a Market Source: what it read, what it kept, and why it failed.
import frappe
from frappe import _
from frappe.model.document import Document


class MarketSourceRun(Document):
	def on_trash(self):
		frappe.throw(_("A run is part of the record and is never deleted."))
