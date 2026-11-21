# SOS-P4-01 a primary project, with the RERA number it is registered under.
import frappe
from frappe import _

from sellos.inventory.base import InventoryRecord, clean_rera_number, squash


class Project(InventoryRecord):
	def validate(self):
		self.stamp_archive()
		self.project_name = squash(self.project_name)
		if not self.project_name:
			frappe.throw(_("Enter the project's name."))
		self.city = squash(self.city)
		self.locality = squash(self.locality)
		self.rera_number = clean_rera_number(self.rera_number, required=True)
		if frappe.db.exists("Project", {"rera_number": self.rera_number, "name": ["!=", self.name]}):
			frappe.throw(
				_("Another project is already registered under RERA number {0}.").format(self.rera_number)
			)
