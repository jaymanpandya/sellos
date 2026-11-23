"""The Channel Partner's own deals, earnings and QR code (SOS-P5-06).

Registering a buyer is SOS-P7-02's method, shared inventory is SOS-P7-03's, and the payout statement is
SOS-P7-04's. This module adds the one read the partner home needs on top of them, and builds no second way to
register, share or pay.

* **Deals.** The deals whose split gives the partner's firm a share, and only that share: the target, the
  booking date, the approval status, the firm's percent and the payout's status and amount. Nothing about the
  other parties of the split, and no other firm's deal. A Deal is not readable by a partner, so the rows are
  picked here by the firm of the signed in partner and nobody else's.
* **Earnings.** Earned so far is the sum of the firm's Paid payouts. Potential future earnings is the sum of its
  payouts that are Due, Approved or On hold. Both are in rupees to two decimals.
* **QR code.** A QR code of the partner's own link, which carries the partner code, as an SVG image the page
  shows. The link opens the company's web app; it makes no public form.

A firm that is not Approved sees none of it (SOS-P7-01), and only a pure partner login may call it.
"""

import base64
import io
from decimal import Decimal

import frappe
import pyqrcode
from frappe import _
from frappe.utils import get_url

from sellos.access.partner_firms import FIRM, firm_of, is_pure_partner, partner_may_work
from sellos.access.registry import sellos_api
from sellos.access.roles import CHANNEL_PARTNER
from sellos.inventory.commissions import _dec, _target
from sellos.sellos.doctype.commission_payout.commission_payout import APPROVED, DUE, HOLD, PAID

PARTNER_PARTY = "Channel Partner"
UNPAID = (DUE, APPROVED, HOLD)


def partner_link(code: str) -> str:
	"""The partner's own link: the company's web app with the partner code."""
	return f"{get_url().rstrip('/')}/sellos/?partner={code}"


def qr_image(link: str) -> str:
	"""A QR code of the link as an SVG data address, for an image tag."""
	buffer = io.BytesIO()
	pyqrcode.create(link, error="M").svg(buffer, scale=4, quiet_zone=2, xmldecl=False)
	return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _deal_rows(firm) -> list[dict]:
	shares = frappe.get_all(
		"Commission Split",
		filters={"parenttype": "Deal", "party_type": PARTNER_PARTY, "partner_firm": firm},
		fields=["parent", "percent"],
	)
	payouts = {
		p.deal: p
		for p in frappe.get_all(
			"Commission Payout",
			filters={"partner_firm": firm},
			fields=["deal", "status", "commission_due"],
		)
	}
	rows = []
	for share in shares:
		deal = frappe.get_doc("Deal", share.parent)
		if deal.archived:
			continue
		payout = payouts.get(deal.name)
		rows.append(
			{
				"name": deal.name,
				"target": _target(deal),
				"deal_date": str(deal.deal_date or ""),
				"approval_status": deal.approval_status,
				"percent": share.percent,
				"payout_status": payout.status if payout else "",
				"commission_due": payout.commission_due if payout else None,
			}
		)
	return sorted(rows, key=lambda r: (r["deal_date"], r["name"]), reverse=True)


def _earnings(firm) -> dict:
	total = {PAID: Decimal(0), "potential": Decimal(0)}
	for payout in frappe.get_all(
		"Commission Payout", filters={"partner_firm": firm}, fields=["status", "commission_due"]
	):
		if payout.status == PAID:
			total[PAID] += _dec(payout.commission_due)
		elif payout.status in UNPAID:
			total["potential"] += _dec(payout.commission_due)
	return {"earned": float(total[PAID]), "potential": float(total["potential"])}


@sellos_api(CHANNEL_PARTNER)
def partner_overview():
	"""The signed in partner's deals, earnings so far, potential earnings and QR code. Only their own firm's."""
	user = frappe.session.user
	if not is_pure_partner(frappe.get_roles(user)):
		frappe.throw(_("This page is for a channel partner login."), frappe.PermissionError)
	firm = firm_of(user)
	if not firm or not partner_may_work(user):
		return {"firm": None, "deals": [], "earned": 0.0, "potential": 0.0, "link": "", "qr": ""}
	link = partner_link(firm)
	return {
		"firm": {"name": firm, "firm_name": frappe.db.get_value(FIRM, firm, "firm_name")},
		"deals": _deal_rows(firm),
		**_earnings(firm),
		"link": link,
		"qr": qr_image(link),
	}
