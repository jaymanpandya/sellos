# SOS-P7-07 a dated price list of a project: a base rate per square foot of carpet area, a floor rise and
# charges. A price list is never changed once made, and never deleted: a new one with a later date takes over
# when its date comes, and the earlier ones stay as they were.
import frappe
from frappe import _

from sellos.inventory.base import InventoryRecord, squash


class PriceList(InventoryRecord):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("A price list is not changed once made. Make a new one with its own date."))
		self.title = squash(self.title)
		if not self.title:
			frappe.throw(_("Enter a title for the price list."))
		if frappe.db.exists("Price List", {"project": self.project, "effective_from": self.effective_from}):
			frappe.throw(
				_("The project already has a price list in force from {0}.").format(self.effective_from)
			)
		seen = set()
		for row in self.charges:
			row.charge_name = squash(row.charge_name)
			if not row.charge_name:
				frappe.throw(_("Enter a name for every charge."))
			if row.charge_name.lower() in seen:
				frappe.throw(_("The charge {0} is listed twice.").format(row.charge_name))
			seen.add(row.charge_name.lower())
			if row.charge_type == "Parking":
				row.always_apply = 1
