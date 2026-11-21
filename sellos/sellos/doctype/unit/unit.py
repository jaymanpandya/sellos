# SOS-P4-01 a unit of a primary project: configuration, carpet area, floor, parking and a status.
import frappe
from frappe import _

from sellos.inventory.base import StatusLogged, squash


class Unit(StatusLogged):
	def validate_record(self):
		self.unit_number = squash(self.unit_number)
		if not self.unit_number:
			frappe.throw(_("Enter the unit number."))
		self.check_measures()
		if frappe.db.exists(
			"Unit",
			{"project": self.project, "unit_number": self.unit_number, "name": ["!=", self.name]},
		):
			frappe.throw(_("Unit {0} is already in this project.").format(self.unit_number))
