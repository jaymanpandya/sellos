"""The readers of the Channel Partner's report panels (SOS-P5-03). The commission statement panel is switched on
by SOS-P7-04, and the deals panel reads the firm's own deals through SOS-P5-06's rows (SOS-LOOP)."""

from frappe.utils import getdate

from sellos.crm.partner_views import _deal_rows
from sellos.inventory.commissions import _statement


def deals(start, end, firm=None, user=None, **context) -> dict:
	"""The firm's own deals dated in the range, one row per deal with only the firm's share. Nothing about the
	other parties of a split, and no other firm's deal."""
	rows = [
		d
		for d in (_deal_rows(firm) if firm else [])
		if d["deal_date"] and getdate(start) <= getdate(d["deal_date"]) <= getdate(end)
	]
	return {
		"columns": [{"field": "commission_due", "label": "Commission", "unit": "rupees"}],
		"rows": [
			{
				"key": d["name"],
				"label": f"{d['target']} ({d['deal_date']}, {d['approval_status']}, {d['percent']}%)",
				"values": [d["commission_due"] or 0],
			}
			for d in rows
		],
		"stats": [{"label": "Deals", "value": len(rows), "unit": "count"}],
	}


def commission(start, end, firm=None, user=None, **context) -> dict:
	"""The partner's own payouts booked in the dates: one row per payout, and the totals. Only the firm's own
	payouts are read, through the permission rules of the signed in partner."""
	statement = (
		_statement(firm, start, end) if firm else {"rows": [], "totals": {"by_status": {}, "total": 0}}
	)
	return {
		"columns": [
			{"field": "commission_due", "label": "Commission due", "unit": "rupees"},
		],
		"rows": [
			{
				"key": r["name"],
				"label": f"{r['target']} ({r['booking_date']}, {r['status']})",
				"values": [r["commission_due"]],
			}
			for r in statement["rows"]
		],
		"stats": [
			{"label": label, "value": statement["totals"]["by_status"].get(status, 0), "unit": "rupees"}
			for label, status in (
				("Due", "Due"),
				("Approved", "Approved"),
				("Paid", "Paid"),
				("On hold", "On hold"),
			)
		],
	}
