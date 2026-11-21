# SOS-P7-07 a payment plan template of a project: instalments as percentages that add up to 100.
from decimal import Decimal

import frappe
from frappe import _

from sellos.inventory.base import InventoryRecord, squash


class PaymentPlan(InventoryRecord):
	def validate(self):
		self.stamp_archive()
		self.plan_name = squash(self.plan_name)
		if not self.plan_name:
			frappe.throw(_("Enter a name for the payment plan."))
		if frappe.db.exists(
			"Payment Plan",
			{"project": self.project, "plan_name": self.plan_name, "name": ["!=", self.name]},
		):
			frappe.throw(_("The project already has a payment plan called {0}.").format(self.plan_name))
		if not self.instalments:
			frappe.throw(_("A payment plan needs at least one instalment."))
		total = Decimal(0)
		last_days = 0
		for number, row in enumerate(self.instalments, start=1):
			row.label = squash(row.label)
			row.due_on = squash(row.due_on)
			if not row.label:
				frappe.throw(_("Enter a name for instalment {0}.").format(number))
			if Decimal(str(row.percent or 0)) <= 0:
				frappe.throw(_("Instalment {0} must be more than 0 percent.").format(number))
			if self.plan_type == "Construction linked" and not row.due_on:
				frappe.throw(_("Instalment {0} needs the construction stage it is due on.").format(number))
			if self.plan_type == "Time linked":
				days = row.days_after_booking or 0
				if days < last_days:
					frappe.throw(
						_("The days after booking must not go down from one instalment to the next.")
					)
				last_days = days
			total += Decimal(str(row.percent))
		if total != Decimal(100):
			frappe.throw(
				_("The instalments add up to {0} percent. They must add up to 100.").format(total.normalize())
			)
