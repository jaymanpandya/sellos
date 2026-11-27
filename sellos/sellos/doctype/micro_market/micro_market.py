# SOS-P3-04 a micro market: a named area a company groups its buildings by. Configurable data, never code.
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from sellos.intel.geo import check_boundary


class MicroMarket(Document):
	def validate(self):
		self.market_name = " ".join((self.market_name or "").split())
		self.parent_area = " ".join((self.parent_area or "").split())
		if not self.market_name:
			frappe.throw(_("Enter the micro market's name."))
		if not self.parent_area:
			frappe.throw(_("Enter the city or region the micro market is in."))
		self.boundary = check_boundary(self.boundary)
		if self.status == "Active":
			self.check_name_is_free()
		self.log_changes()

	def check_name_is_free(self):
		"""Two active micro markets of one country never share a name."""
		clash = frappe.db.get_value(
			"Micro Market",
			{
				"market_name": self.market_name,
				"country": self.country,
				"status": "Active",
				"name": ["!=", self.name or ""],
			},
			"name",
		)
		if clash:
			frappe.throw(_("An active micro market called {0} already exists.").format(self.market_name))

	def log_changes(self):
		"""Every rename, boundary edit, archive and restore is kept in the history, whichever way it is saved."""
		if self.is_new():
			self.add_history("Created", self.market_name)
			return
		before = self.get_doc_before_save()
		if not before:
			return
		if before.market_name != self.market_name:
			self.add_history("Renamed", f"{before.market_name} to {self.market_name}")
		if (before.boundary or "") != (self.boundary or ""):
			self.add_history("Boundary changed", "")
		if before.status != self.status and not self.flags.history_kind:
			self.add_history("Archived" if self.status == "Archived" else "Restored", "")
		if self.flags.history_kind:
			self.add_history(self.flags.history_kind, self.flags.history_detail or "")

	def add_history(self, kind, detail):
		self.append(
			"history",
			{
				"changed_on": now_datetime(),
				"changed_by": frappe.session.user,
				"change_kind": kind,
				"detail": detail,
			},
		)

	def on_trash(self):
		frappe.throw(_("A micro market is archived, never deleted."), frappe.PermissionError)
