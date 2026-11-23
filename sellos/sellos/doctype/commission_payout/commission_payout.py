# SOS-P7-04 what the company owes one channel partner firm on one deal, and where it is on the way to payment:
# Due, Approved, Paid, or On hold with a reason. The figures are worked out when the deal's split is approved and
# are never typed. Paid is final and records the payment reference and date. Nothing is deleted.
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

DUE = "Due"
APPROVED = "Approved"
PAID = "Paid"
HOLD = "On hold"
STATUSES = (DUE, APPROVED, PAID, HOLD)
FIGURES = (
	"deal",
	"partner_firm",
	"project",
	"booking_date",
	"agreement_value",
	"rate",
	"rate_basis",
	"commission_total",
	"partner_percent",
	"commission_due",
)
# From each status, where a payout may go. A held payout goes back to the status it was held from.
MOVES = {DUE: (APPROVED, HOLD), APPROVED: (PAID, HOLD), HOLD: (DUE, APPROVED), PAID: ()}


class CommissionPayout(Document):
	def validate(self):
		before = None if self.is_new() else self.get_doc_before_save()
		if self.status not in STATUSES:
			frappe.throw(_("A payout is Due, Approved, Paid or On hold."))
		if before is None:
			self.status = DUE
			return
		if not self.flags.recalculating and any(
			str(self.get(f) or "") != str(before.get(f) or "") for f in FIGURES
		):
			frappe.throw(_("The figures of a payout are worked out, not typed."))
		if before.status == PAID and (
			self.status != PAID
			or self.payment_reference != before.payment_reference
			or str(self.paid_on or "") != str(before.paid_on or "")
		):
			frappe.throw(_("A paid payout is not changed."))
		if self.status != before.status:
			self.check_move(before)

	def check_move(self, before):
		if self.status not in MOVES[before.status]:
			frappe.throw(_("A payout can not go from {0} to {1}.").format(_(before.status), _(self.status)))
		if before.status == HOLD and self.status != before.held_from:
			frappe.throw(_("A held payout goes back to {0}.").format(_(before.held_from)))
		if self.status == HOLD:
			self.hold_reason = " ".join(str(self.hold_reason or "").split())
			if not self.hold_reason:
				frappe.throw(_("Give the reason the payout is on hold."))
			self.held_from = before.status
		else:
			self.hold_reason = self.held_from = None
		if self.status == APPROVED and before.status != HOLD:
			self.approved_by, self.approved_on = frappe.session.user, now_datetime()
		if self.status == PAID:
			self.payment_reference = " ".join(str(self.payment_reference or "").split())
			if not self.payment_reference:
				frappe.throw(_("Enter the payment reference."))
			if not self.paid_on:
				frappe.throw(_("Enter the date it was paid."))
			self.paid_on = getdate(self.paid_on)
			if self.paid_on > getdate(today()):
				frappe.throw(_("The payment date can not be in the future."))

	def on_trash(self):
		frappe.throw(_("Payouts are kept, never deleted."), frappe.PermissionError)
