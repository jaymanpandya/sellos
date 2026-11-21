# SOS-P7-05 an amenity in the list the Company Admin keeps, from which a project's amenities are chosen.
import frappe
from frappe import _

from sellos.inventory.base import InventoryRecord, squash


class Amenity(InventoryRecord):
	def validate(self):
		self.stamp_archive()
		self.amenity_name = squash(self.amenity_name)
		if not self.amenity_name:
			frappe.throw(_("Enter the amenity's name."))
