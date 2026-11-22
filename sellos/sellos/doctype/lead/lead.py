# P1.06 (requirements: SOS-P1-15) an enquiry from a client. Activities, tasks and site visits attach to it.
import frappe
from frappe import _

from sellos.access.lead_permissions import check_assignee_in_team
from sellos.access.partner_registrations import check_partner_change
from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN
from sellos.crm import assignment
from sellos.crm.base import ArchiveOnly, stamp_archive
from sellos.crm.lead_sources import check_usable
from sellos.crm.notifications import notify_lead_assignment
from sellos.crm.pipeline import BUYER, PIPELINES, check_stage_pipeline, first_stage
from sellos.crm.requirements import validate_requirements

CAN_BE_ASSIGNED = frozenset({AGENT, CHANNEL_PARTNER, COMPANY_ADMIN})


class Lead(ArchiveOnly):
	def before_insert(self):
		assignment.assign_new(self)  # SOS-P1-19: every new lead reaches an agent by the rules

	def validate(self):
		self.lead_title = self.lead_title or self._title()
		if self.assigned_to:
			self._check_assignee()
			check_assignee_in_team(self)  # SOS-P1-18
		check_partner_change(self)  # SOS-P7-02: only the registration and a Company Admin set the partner
		check_usable(self)
		self.pipeline = self.pipeline or BUYER
		if self.pipeline not in PIPELINES:
			frappe.throw(_("A lead is on the Buyer or the Seller pipeline."))
		self.stage = self.stage or first_stage(self.pipeline)  # SOS-P1-07, SOS-P4-04
		check_stage_pipeline(self, self.stage)
		validate_requirements(self)
		stamp_archive(self)

	def _title(self):
		name = frappe.db.get_value("Client", self.client, "client_name") if self.client else None
		return f"{name} {self.source}".strip() if self.source else (name or "")

	def _check_assignee(self):
		if not (set(frappe.get_roles(self.assigned_to)) & CAN_BE_ASSIGNED):
			frappe.throw(_("{0} cannot be assigned leads.").format(self.assigned_to))

	def on_update(self):
		assignment.on_lead_saved(self)  # SOS-P1-19: the log, and the follow ups and visits move
		notify_lead_assignment(self)  # SOS-P1-23
