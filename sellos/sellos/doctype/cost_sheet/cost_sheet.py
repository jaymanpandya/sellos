# SOS-P7-07 a cost sheet of a unit. It is made by sellos.inventory.cost_sheet from the price list in force,
# the company's percentages and a payment plan, and it keeps what it used. It is never changed and never
# deleted, so a later price change leaves it as it was issued.
import frappe
from frappe import _
from frappe.model.document import Document


class CostSheet(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("A cost sheet is not changed once issued. Make a new one."))

	def on_trash(self):
		frappe.throw(_("Cost sheets are kept, never deleted."), frappe.PermissionError)
