# SOS-P3-04 one correction of a building: the field, its old value, who changed it and when. Written once.
import frappe
from frappe import _
from frappe.model.document import Document


class BuildingCorrection(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("A correction is never changed."), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("A correction is never deleted."), frappe.PermissionError)
