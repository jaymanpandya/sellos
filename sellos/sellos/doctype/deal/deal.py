# SOS-P4-06 a deal: a client buys a unit or a property at a price, and the commission is split among the agent,
# the channel partner firm and the company. The percents of the split add up to 100, and a Company Admin approves
# the split. An approved split, and the deal it belongs to, are not changed unless the split is reopened.
# A deal is archived, never deleted.
from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

from sellos.access.roles import AGENT, SALES_MANAGER
from sellos.inventory.base import InventoryRecord
from sellos.sellos.doctype.channel_partner_firm.channel_partner_firm import APPROVED as FIRM_APPROVED

PENDING = "Pending approval"
APPROVED = "Approved"
AGENT_PARTY = "Agent"
PARTNER_PARTY = "Channel Partner"
COMPANY_PARTY = "Company"
PARTIES = (AGENT_PARTY, PARTNER_PARTY, COMPANY_PARTY)
HUNDRED = Decimal("100")
CENT = Decimal("0.01")
LOCKED = ("client", "lead", "unit", "property", "price", "deal_date", "commission_amount")


def _dec(value) -> Decimal:
	return Decimal(str(flt(value))).quantize(CENT, rounding=ROUND_HALF_UP)


def split_amounts(total, percents) -> list[Decimal]:
	"""Share a commission by percents that add up to 100, to the paisa. Each share is rounded to the paisa and
	any paisa left over (or over) goes to the biggest share, so the shares always add up to the commission."""
	total = _dec(total)
	shares = [(total * _dec(p) / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP) for p in percents]
	if shares:
		biggest = max(range(len(shares)), key=lambda i: _dec(percents[i]))
		shares[biggest] += total - sum(shares)
	return shares


class Deal(InventoryRecord):
	def validate(self):
		before = None if self.is_new() else self.get_doc_before_save()
		self.stamp_archive()
		self.check_deal()
		self.check_splits()
		self.check_approval(before)
		self.share_commission()

	def check_deal(self):
		if not self.client or not frappe.db.exists("Client", self.client):
			frappe.throw(_("Choose the client who is buying."))
		if bool(self.unit) == bool(self.property):
			frappe.throw(_("A deal is for a unit or for a property: choose one of them."))
		target, name = ("Unit", self.unit) if self.unit else ("Property", self.property)
		if not frappe.db.exists(target, name):
			frappe.throw(_("There is no {0} {1}.").format(_(target).lower(), name))
		self.price = flt(self.price)
		if self.price <= 0:
			frappe.throw(_("Enter the price of the deal, more than zero."))
		self.commission_amount = flt(self.commission_amount)
		if self.commission_amount < 0 or self.commission_amount > self.price:
			frappe.throw(_("The commission is from zero to the price of the deal."))
		if self.lead:
			client = frappe.db.get_value("Lead", self.lead, "client")
			if client is None and not frappe.db.exists("Lead", self.lead):
				frappe.throw(_("There is no lead {0}.").format(self.lead))
			if client != self.client:
				frappe.throw(_("The lead {0} belongs to another client.").format(self.lead))
		self.deal_date = getdate(self.deal_date or today())

	def check_splits(self):
		"""Every share names its party, no party is listed twice and the percents add up to exactly 100."""
		if not self.splits:
			frappe.throw(_("Add the commission split. It must add up to 100 percent."))
		seen = set()
		total = Decimal(0)
		for row in self.splits:
			if row.party_type not in PARTIES:
				frappe.throw(_("A share is for the agent, the channel partner or the company."))
			key = self.check_party(row)
			if key in seen:
				frappe.throw(_("{0} is listed twice in the split.").format(key[1] or _("The company")))
			seen.add(key)
			row.percent = float(_dec(row.percent))
			if not 0 < row.percent <= 100:
				frappe.throw(_("A share is above 0 and up to 100 percent."))
			total += _dec(row.percent)
		if total != HUNDRED:
			frappe.throw(
				_("The split adds up to {0} percent. It must add up to exactly 100 percent.").format(total)
			)

	def check_party(self, row):
		if row.party_type == COMPANY_PARTY:
			row.agent = row.partner_firm = None
			return (COMPANY_PARTY, None)
		if row.party_type == AGENT_PARTY:
			row.partner_firm = None
			roles = frappe.get_roles(row.agent) if row.agent and frappe.db.exists("User", row.agent) else []
			if AGENT not in roles and SALES_MANAGER not in roles:
				frappe.throw(_("Choose the agent who earns this share."))
			return (AGENT_PARTY, row.agent)
		row.agent = None
		if not row.partner_firm or not frappe.db.exists("Channel Partner Firm", row.partner_firm):
			frappe.throw(_("Choose the channel partner firm who earns this share."))
		if frappe.db.get_value("Channel Partner Firm", row.partner_firm, "status") != FIRM_APPROVED:
			frappe.throw(_("{0} is not an approved firm.").format(row.partner_firm))
		return (PARTNER_PARTY, row.partner_firm)

	def check_approval(self, before):
		if self.approval_status not in (PENDING, APPROVED):
			frappe.throw(_("A split is Pending approval or Approved."))
		approving = self.approval_status == APPROVED and (not before or before.approval_status != APPROVED)
		if approving and not self.flags.approving:
			frappe.throw(_("A Company Admin approves the split."), frappe.PermissionError)
		if self.approval_status == PENDING:
			self.approved_by = self.approved_on = None
		if not before or before.approval_status != APPROVED or self.approval_status != APPROVED:
			return
		changed = any(str(self.get(f) or "") != str(before.get(f) or "") for f in LOCKED)
		old = [(r.party_type, r.agent or "", r.partner_firm or "", flt(r.percent)) for r in before.splits]
		new = [(r.party_type, r.agent or "", r.partner_firm or "", flt(r.percent)) for r in self.splits]
		if changed or old != new:
			frappe.throw(_("An approved split is not changed. Reopen it first."))

	def share_commission(self):
		amounts = split_amounts(self.commission_amount, [r.percent for r in self.splits])
		for row, amount in zip(self.splits, amounts, strict=True):
			row.amount = float(amount)

	def on_update(self):
		# SOS-P7-04: an approved split makes the channel partner's payout (Due), from the rate in force on the
		# deal date. It is safe to run on every save: a payout is made once, and only a Due one is worked out again.
		if self.approval_status == APPROVED:
			from sellos.inventory.commissions import make_payouts

			make_payouts(self)

	def approve(self):
		self.flags.approving = True
		self.approval_status = APPROVED
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
