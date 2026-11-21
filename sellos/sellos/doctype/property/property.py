# SOS-P4-01 a secondary property: a resale or rental property outside the company's primary projects.
import frappe
from frappe import _

from sellos.inventory.base import StatusLogged, clean_rera_number, squash


class Property(StatusLogged):
	def validate_record(self):
		self.title = squash(self.title)
		if not self.title:
			frappe.throw(_("Enter a title for the property."))
		self.city = squash(self.city)
		self.rera_number = clean_rera_number(self.rera_number)
		self.check_measures()
