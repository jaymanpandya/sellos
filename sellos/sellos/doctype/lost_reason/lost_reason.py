# SOS-P1-21 a lost reason from the list a Company Admin keeps. A reason in use is disabled, never deleted.
import frappe
from frappe import _
from frappe.model.document import Document

from sellos.crm import call_outcomes


class LostReason(Document):
	def before_insert(self):
		self.reason_name = " ".join((self.reason_name or "").split())

	def validate(self):
		if not self.is_new() and self.has_value_changed("reason_name"):
			frappe.throw(_("A reason keeps its name. Disable it and add a new one."))

	def on_trash(self):
		call_outcomes.ensure_reason_deletable(self.name)
