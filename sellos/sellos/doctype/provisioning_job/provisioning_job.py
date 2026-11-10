# P1.01 one request to make a tenant's site. The worker that runs it is P1.02.
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from sellos.provisioning import status


class ProvisioningJob(Document):
	def validate(self):
		if self.is_new():
			status.check_new(self)
			self.attempts = 0
			return
		status.check_change(self)
		self._keep_counters()
		if self.has_value_changed("status"):
			self._stamp()

	def _keep_counters(self):
		"""The attempt count and the times are the server's. A caller can not set them."""
		before = self.get_doc_before_save()
		for field in ("attempts", "started_at", "finished_at"):
			self.set(field, before.get(field))

	def _stamp(self):
		if self.status == status.PROVISIONING:
			self.attempts = cint(self.attempts) + 1
			self.started_at = now_datetime()
			self.finished_at = None
		elif self.status in (status.ACTIVE, status.FAILED):
			self.finished_at = now_datetime()

	def on_trash(self):
		frappe.throw(_("Provisioning jobs are kept as a record, never deleted."), frappe.PermissionError)
