# P1.06 a visit to a property. SOS-P1-25 adds the agent, the confirmation and the outcome.
import frappe
from frappe.utils import now_datetime

from sellos.crm.base import ArchiveOnly, stamp_archive


class SiteVisit(ArchiveOnly):
	def validate(self):
		stamp_archive(self)
		if not self.agent and self.lead:  # the lead's agent takes the visit unless another is chosen
			self.agent = frappe.db.get_value("Lead", self.lead, "assigned_to")
		self.sync_cancellation()
		if self.has_value_changed("confirmation_status") and not self.is_new():
			self.confirmed_on = now_datetime()

	def on_update(self):
		from sellos.access.partner_registrations import on_site_visit_saved

		on_site_visit_saved(self)  # SOS-P7-02: a done visit moves a partner's registration to Visited

	def sync_cancellation(self):
		"""A cancelled visit and a Cancelled confirmation say the same thing, so one sets the other."""
		if self.is_new() or self.has_value_changed("status"):
			if self.status == "Cancelled":
				self.confirmation_status = "Cancelled"
		if self.confirmation_status == "Cancelled" and self.status == "Scheduled":
			self.status = "Cancelled"
