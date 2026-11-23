# SOS-P3-01 one registration data source and how often it runs. Lives on the control site.
import frappe
from frappe import _
from frappe.model.document import Document

from sellos.intel import adapters


class MarketSource(Document):
	def validate(self):
		if self.adapter not in adapters.kinds():
			frappe.throw(_("Choose an adapter that exists."))
		if self.adapter == "File" and not (self.file_name or "").strip():
			frappe.throw(_("Name the export file."))

	def on_trash(self):
		frappe.throw(_("A source is switched off, never deleted."))
