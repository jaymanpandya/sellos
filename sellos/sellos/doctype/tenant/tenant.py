# P1.01 a company on SellOS: one site and one database each, named from its tenant id.
import frappe
from frappe import _
from frappe.model.document import Document

from sellos.provisioning import status
from sellos.provisioning.tenant_sites import TenantNameError, names


class Tenant(Document):
	def validate(self):
		if not self.is_new() and self.has_value_changed("tenant_id"):
			frappe.throw(_("A tenant ID can not be changed. It names the company's site and database."))
		self._name_the_site()
		if self.is_new():
			status.check_new(self)
		else:
			status.check_change(self)
		if self.plan and not frappe.db.get_value("Plan", self.plan, "enabled"):
			frappe.throw(_("Plan {0} is switched off.").format(self.plan))

	def _name_the_site(self):
		"""The site and database come from the one name function, so only a safe id is accepted."""
		self.tenant_id = (self.tenant_id or "").strip()
		try:
			self.site_name, self.db_name = names(self.tenant_id)
		except TenantNameError as e:
			frappe.throw(str(e))

	def after_insert(self):
		"""Asking for a company asks for its site: the worker (P1.02) picks the job up."""
		frappe.get_doc({"doctype": "Provisioning Job", "tenant": self.name}).insert(ignore_permissions=True)

	def on_trash(self):
		frappe.throw(_("Tenants are kept as a record, never deleted."), frappe.PermissionError)
