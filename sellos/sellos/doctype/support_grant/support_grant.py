# P1.13 a time limited grant that lets one Platform Admin read this company's records.
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, now_datetime

from sellos.access.roles import PLATFORM_ADMIN

MAX_MINUTES = 240  # 4 hours, the most a grant may last (P1.13)
FIXED_FIELDS = ("support_user", "duration_minutes", "granted_by", "starts_at", "expires_at")


class SupportGrant(Document):
	def validate(self):
		if self.is_new():
			self._start()
		else:
			self._keep_terms()

	def _start(self):
		minutes = cint(self.duration_minutes)
		if not 1 <= minutes <= MAX_MINUTES:
			frappe.throw(_("Choose a duration from 1 minute to 4 hours."))
		if not frappe.db.get_value("User", self.support_user, "enabled"):
			frappe.throw(_("{0} is not an active user.").format(self.support_user))
		if PLATFORM_ADMIN not in frappe.get_roles(self.support_user):
			frappe.throw(_("Support access can only be given to a support user."))
		# The server sets the clock and the author. A caller can not choose either.
		self.duration_minutes = minutes
		self.granted_by = frappe.session.user
		self.starts_at = now_datetime()
		self.expires_at = add_to_date(self.starts_at, minutes=minutes)
		self.status = "Active"

	def _keep_terms(self):
		"""Once given, a grant can only be ended. Its length and its holder never change."""
		for field in FIXED_FIELDS:
			if self.has_value_changed(field):
				frappe.throw(_("A support grant can not be changed. Revoke it and make a new one."))

	def on_trash(self):
		frappe.throw(_("Support grants are kept as a record, never deleted."), frappe.PermissionError)
