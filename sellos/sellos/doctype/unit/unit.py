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
		self.tower = self.tower or None
		if self.tower and frappe.db.get_value("Project Tower", self.tower, "project") != self.project:
			frappe.throw(_("The tower or wing is not part of this project."))
		# SOS-P7-05: a unit number is unique within its tower, or within the project when it has no tower.
		same = {"project": self.project, "tower": self.tower or ["is", "not set"]}
		if frappe.db.exists("Unit", {**same, "unit_number": self.unit_number, "name": ["!=", self.name]}):
			frappe.throw(
				_("Unit {0} is already in this tower.").format(self.unit_number)
				if self.tower
				else _("Unit {0} is already in this project.").format(self.unit_number)
			)
