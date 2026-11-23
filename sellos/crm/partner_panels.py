"""The readers of the Channel Partner's report panels (SOS-P5-03). The commission statement panel is switched on
by SOS-P7-04. The deals panel has no reader yet, so it still shows as waiting."""

from sellos.inventory.commissions import _statement


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
