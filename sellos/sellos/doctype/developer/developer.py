# SOS-P4-01 a developer: the company that builds a project.
import frappe
from frappe import _
from frappe.utils import validate_email_address

from sellos.inventory.base import InventoryRecord, clean_rera_number, squash


class Developer(InventoryRecord):
	def validate(self):
		self.stamp_archive()
		self.developer_name = squash(self.developer_name)
		if not self.developer_name:
			frappe.throw(_("Enter the developer's name."))
		self.rera_registration = clean_rera_number(self.rera_registration)
		self.email = (self.email or "").strip().lower()
		if self.email and not validate_email_address(self.email):
			frappe.throw(_("Enter a valid email address."))
