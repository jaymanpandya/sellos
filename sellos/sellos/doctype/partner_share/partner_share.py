# SOS-P7-03 what one project shares with one partner firm, or with every Approved firm: all its units or
# chosen ones, its price list in force, and chosen brochures. A share is withdrawn, never deleted, and every
# share and withdrawal is logged with who did it and when.
import frappe
from frappe import _
from frappe.utils import now_datetime

from sellos.crm.base import ArchiveOnly
from sellos.sellos.doctype.channel_partner_firm.channel_partner_firm import APPROVED

ACTIVE = "Active"
WITHDRAWN = "Withdrawn"


class PartnerShare(ArchiveOnly):
	def validate(self):
		if not self.is_new() and self.get_doc_before_save().status == WITHDRAWN:
			frappe.throw(_("A withdrawn share can not be changed. Share the project again instead."))
		self.check_target()
		self.check_contents()
		if self.is_new():
			self.status = ACTIVE
			self.note("Shared", self.describe())
		elif self.flags.withdrawing:
			self.status = WITHDRAWN
			self.withdrawn_on = now_datetime()
			self.withdrawn_by = frappe.session.user
			self.withdrawn_reason = (self.flags.withdraw_reason or "").strip()
			self.note("Withdrawn", self.withdrawn_reason)
		elif self.has_changed_contents():
			self.note("Changed", self.describe())

	def check_target(self):
		if self.all_firms:
			self.partner_firm = None
			return
		if not self.partner_firm:
			frappe.throw(_("Choose a partner firm, or share with every Approved firm."))
		if (
			self.is_new()
			and frappe.db.get_value("Channel Partner Firm", self.partner_firm, "status") != APPROVED
		):
			frappe.throw(_("A project is shared only with an Approved firm."))

	def check_contents(self):
		if frappe.db.get_value("Project", self.project, "archived"):
			frappe.throw(_("An archived project can not be shared."))
		if self.all_units:
			self.units = []
		elif not self.units:
			frappe.throw(_("Choose the units to share, or share all of them."))
		seen = set()
		for row in list(self.units):
			if row.unit in seen:
				self.remove(row)
				continue
			seen.add(row.unit)
			if frappe.db.get_value("Unit", row.unit, "project") != self.project:
				frappe.throw(_("Unit {0} is not in this project.").format(row.unit))
		seen = set()
		for row in list(self.brochures):
			if row.media_asset in seen:
				self.remove(row)
				continue
			seen.add(row.media_asset)
			if frappe.db.get_value("Media Asset", row.media_asset, "archived"):
				frappe.throw(_("{0} is archived and can not be shared.").format(row.media_asset))

	def has_changed_contents(self) -> bool:
		before = self.get_doc_before_save()
		return (
			bool(before.all_units) != bool(self.all_units)
			or bool(before.share_price_list) != bool(self.share_price_list)
			or sorted(r.unit for r in before.units) != sorted(r.unit for r in self.units)
			or sorted(r.media_asset for r in before.brochures)
			!= sorted(r.media_asset for r in self.brochures)
		)

	def describe(self) -> str:
		who = _("every Approved firm") if self.all_firms else self.partner_firm
		units = _("all units") if self.all_units else _("{0} units").format(len(self.units))
		parts = [_("{0} with {1}").format(self.project, who), units]
		if self.share_price_list:
			parts.append(_("price list"))
		if self.brochures:
			parts.append(_("{0} brochures").format(len(self.brochures)))
		return ", ".join(parts)

	def note(self, action, detail=""):
		self.append(
			"log",
			{
				"changed_on": now_datetime(),
				"changed_by": frappe.session.user,
				"action": action,
				"detail": detail,
			},
		)
