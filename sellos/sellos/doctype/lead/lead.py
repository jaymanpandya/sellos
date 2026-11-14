# P1.06 (requirements: SOS-P1-15) an enquiry from a client. Activities, tasks and site visits attach to it.
import frappe
from frappe import _

from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN
from sellos.crm.base import ArchiveOnly, stamp_archive
from sellos.crm.requirements import validate_requirements

CAN_BE_ASSIGNED = frozenset({AGENT, CHANNEL_PARTNER, COMPANY_ADMIN})


class Lead(ArchiveOnly):
	def validate(self):
		self.lead_title = self.lead_title or self._title()
		if self.assigned_to:
			self._check_assignee()
		validate_requirements(self)
		stamp_archive(self)

	def _title(self):
		name = frappe.db.get_value("Client", self.client, "client_name") if self.client else None
		return f"{name} {self.source}".strip() if self.source else (name or "")

	def _check_assignee(self):
		if not (set(frappe.get_roles(self.assigned_to)) & CAN_BE_ASSIGNED):
			frappe.throw(_("{0} cannot be assigned leads.").format(self.assigned_to))
