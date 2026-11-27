# SOS-P3-04 a building on the platform master. Lives on the control site only, curated by the Platform Admin.
import frappe
from frappe import _
from frappe.model.document import Document

from sellos.inventory.base import clean_rera_number, squash


class PlatformBuilding(Document):
	def validate(self):
		self.building_name = squash(self.building_name)
		if not self.building_name:
			frappe.throw(_("Enter the building's name."))
		self.rera_number = clean_rera_number(self.rera_number)

	def on_trash(self):
		frappe.throw(_("A building is never deleted."), frappe.PermissionError)
