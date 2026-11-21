# SOS-P7-05 a tower or wing of a project, with its floors. Its units are Units that name it.
import frappe
from frappe import _
from frappe.utils import cint

from sellos.inventory.base import InventoryRecord, squash


class ProjectTower(InventoryRecord):
	def validate(self):
		self.stamp_archive()
		self.tower_name = squash(self.tower_name)
		if not self.tower_name:
			frappe.throw(_("Enter the name of the tower or wing."))
		if frappe.db.exists(
			"Project Tower",
			{"project": self.project, "tower_name": self.tower_name, "name": ["!=", self.name]},
		):
			frappe.throw(_("{0} is already a tower or wing of this project.").format(self.tower_name))
		seen = set()
		for row in self.floors:
			row.floor_number = cint(row.floor_number)
			row.floor_label = squash(row.floor_label)
			if row.floor_number in seen:
				frappe.throw(_("Floor {0} is listed twice.").format(row.floor_number))
			seen.add(row.floor_number)
		self.floors.sort(key=lambda row: row.floor_number)
		for index, row in enumerate(self.floors, start=1):
			row.idx = index
