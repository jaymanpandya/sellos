# SOS-P1-21 a call outcome from the list a Company Admin keeps. An outcome in use is disabled, never deleted.
import frappe
from frappe import _
from frappe.model.document import Document

from sellos.crm import call_outcomes


class CallOutcome(Document):
	def before_insert(self):
		self.outcome_name = " ".join((self.outcome_name or "").split())

	def validate(self):
		# Reports group calls by the name, so it is set once.
		if not self.is_new() and self.has_value_changed("outcome_name"):
			frappe.throw(_("An outcome keeps its name. Disable it and add a new one."))

	def on_trash(self):
		call_outcomes.ensure_outcome_deletable(self.name)
