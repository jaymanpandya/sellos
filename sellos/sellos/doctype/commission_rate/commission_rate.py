# SOS-P7-04 a commission rate: what a project pays on a deal, as a percent of the agreement value or a fixed
# amount, from a start date. A channel partner firm may have a rate of its own that overrides the project's.
# A rate is never changed or deleted: a new rate with a later start date replaces it, and the earlier ones are
# kept. Only a rate that was entered by mistake is archived.
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import flt, getdate

from sellos.inventory.base import InventoryRecord

PERCENTAGE = "Percentage"
FIXED = "Fixed amount"
RATE_TYPES = (PERCENTAGE, FIXED)
LOCKED = ("project", "partner_firm", "rate_type", "value", "start_date")


class CommissionRate(InventoryRecord):
	def validate(self):
		before = None if self.is_new() else self.get_doc_before_save()
		self.stamp_archive()
		if before:
			if any(str(self.get(f) or "") != str(before.get(f) or "") for f in LOCKED):
				frappe.throw(_("A rate is not changed. Add a new rate with a later start date."))
			return
		self.check_rate()

	def check_rate(self):
		if not self.project or not frappe.db.exists("Project", self.project):
			frappe.throw(_("Choose the project this rate is for."))
		if self.partner_firm and not frappe.db.exists("Channel Partner Firm", self.partner_firm):
			frappe.throw(_("There is no partner firm {0}.").format(self.partner_firm))
		if self.rate_type not in RATE_TYPES:
			frappe.throw(_("A rate is a percentage or a fixed amount."))
		self.value = float(Decimal(str(flt(self.value))).quantize(Decimal("0.01")))
		if self.value <= 0:
			frappe.throw(_("Enter the rate, more than zero."))
		if self.rate_type == PERCENTAGE and self.value > 100:
			frappe.throw(_("A percentage rate is up to 100."))
		if not self.start_date:
			frappe.throw(_("Enter the date the rate starts."))
		self.start_date = getdate(self.start_date)
		same = {
			"project": self.project,
			"partner_firm": self.partner_firm or ("is", "not set"),
			"start_date": self.start_date,
			"archived": 0,
		}
		if frappe.db.exists("Commission Rate", {**same, "name": ("!=", self.name or "")}):
			frappe.throw(_("There is already a rate that starts on that date. Choose a later date."))
