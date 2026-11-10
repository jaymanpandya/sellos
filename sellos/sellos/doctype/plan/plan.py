# P1.01 a plan stub: a name, a switch and a user limit. The tiers and prices come with P6.02.
import frappe
from frappe import _
from frappe.model.document import Document


class Plan(Document):
	def validate(self):
		if (self.max_users or 0) < 0:
			frappe.throw(_("The most users can not be less than 0."))

	def on_trash(self):
		frappe.throw(_("Plans are kept as a record. Switch one off instead."), frappe.PermissionError)
