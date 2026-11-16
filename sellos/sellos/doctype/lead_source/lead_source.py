# SOS-P1-20 a lead source from the list a Company Admin keeps. A source in use cannot be deleted. It is disabled.
import frappe
from frappe import _
from frappe.model.document import Document

from sellos.crm import lead_sources


class LeadSource(Document):
	def before_insert(self):
		self.source_name = " ".join((self.source_name or "").split())

	def validate(self):
		# Reports group leads by the name, so it is set once.
		if not self.is_new() and self.has_value_changed("source_name"):
			frappe.throw(_("A source keeps its name. Disable it and add a new one."))

	def on_trash(self):
		lead_sources.ensure_deletable(self.name)
