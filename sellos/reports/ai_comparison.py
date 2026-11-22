"""The AI against human calling comparison (SOS-P5-09): six measures for the AI calls of a range of dates,
the human calls of the same range, and the human baseline, each worked out from the Call Log alone.

Every figure comes from one list of Call Logs (`_calls`) and one test per measure (`_measure_matches`).
The report adds the list up and the drill down returns the rows the same test keeps, so a figure can never
differ from the Call Log, nor from the calls behind it.

* A call is AI when its Call Log mode is AI, and human otherwise (Manual, SOS-P2-05).
* The date of a call is the date of its `started_on`. A range includes both end days.
* The human baseline is human calls only. It is the four weeks (28 days) that end the day before the range
  starts, unless the reader gives its own dates.
* Connected is as in SOS-P2-11: the provider says completed and the call ran for more than 0 seconds.
* Connect rate: connected calls as a percent of calls.
* Qualified: a connected call whose outcome is Interested or Site visit booked. Qualified lead rate:
  qualified calls as a percent of connected calls.
* Site visits booked: connected calls whose outcome is Site visit booked.
* Cost per qualified lead: the rupees of every call in the group (connected or not, exact decimals)
  divided by its qualified calls. It is empty when there is none.
* Handover rate: AI calls handed to a human as a percent of connected AI calls. Humans are never handed
  over, so it is empty for the human groups.
* Complaints: calls whose outcome is Complaint, an outcome a Company Admin adds to the Call Outcome list.
  A company with no such outcome has none.

Consent never blocks anything here: the report reads no consent status.
"""

from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_days, getdate

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.crm.call_outcomes import INTERESTED, SITE_VISIT_BOOKED
from sellos.reports.calls import _percent, _range

COMPLAINT = "Complaint"
QUALIFYING = (INTERESTED, SITE_VISIT_BOOKED)
BASELINE_DAYS = 28
GROUPS = ("ai", "human", "baseline")
MEASURES = ("connected", "qualified", "site_visits", "handovers", "complaints")


def _baseline_range(start, baseline_from, baseline_to):
	"""The baseline's two days: the dates given, or the 28 days that end the day before `start`."""
	end = getdate(baseline_to) if baseline_to else add_days(start, -1)
	first = getdate(baseline_from) if baseline_from else add_days(end, -(BASELINE_DAYS - 1))
	if first > end:
		frappe.throw(_("The baseline start date is after its end date."))
	return first, end


def _calls(start, end):
	"""Every Call Log the reader may read that started between the two days, with the fields the measures use."""
	rows = frappe.get_list(
		"Call Log",
		filters=[
			["started_on", ">=", f"{start} 00:00:00"],
			["started_on", "<", f"{add_days(end, 1)} 00:00:00"],
		],
		fields=[
			"name",
			"lead",
			"mode",
			"state",
			"duration",
			"cost_rupees",
			"outcome",
			"handed_over",
			"started_on",
		],
		order_by="started_on desc, name desc",
		limit_page_length=0,
	)
	for row in rows:
		row.is_ai = row.mode == "AI"
		row.connected = row.state == "completed" and (row.duration or 0) > 0
		row.qualified = row.connected and row.outcome in QUALIFYING
		row.site_visit = row.connected and row.outcome == SITE_VISIT_BOOKED
		row.handover = row.is_ai and row.connected and bool(row.handed_over)
		row.complaint = row.outcome == COMPLAINT
		row.cost = Decimal(str(row.cost_rupees or 0))
	return rows


def _measure_matches(row, measure):
	"""Whether the call counts towards a measure's figure. No measure keeps every call."""
	return measure is None or bool(
		{
			"connected": row.connected,
			"qualified": row.qualified,
			"site_visits": row.site_visit,
			"handovers": row.handover,
			"complaints": row.complaint,
		}[measure]
	)


def _measures(rows, ai):
	"""The six measures for one group of calls, with the counts they are made from."""
	calls = len(rows)
	counts = {m: sum(1 for r in rows if _measure_matches(r, m)) for m in MEASURES}
	cost = sum((r.cost for r in rows), Decimal(0))
	return {
		"calls": calls,
		**counts,
		"cost": float(cost),
		"connect_rate": _percent(counts["connected"], calls),
		"qualified_rate": _percent(counts["qualified"], counts["connected"]),
		"cost_per_qualified": (
			float((cost / counts["qualified"]).quantize(Decimal("0.01"))) if counts["qualified"] else None
		),
		"handover_rate": _percent(counts["handovers"], counts["connected"]) if ai else None,
	}


def _groups(start, end, first, last):
	"""The calls of each group: AI and human for the range, human for the baseline."""
	ranged = _calls(start, end)
	baseline = [r for r in _calls(first, last) if not r.is_ai]
	return {
		"ai": [r for r in ranged if r.is_ai],
		"human": [r for r in ranged if not r.is_ai],
		"baseline": baseline,
	}


def _difference(ai, baseline):
	"""AI minus the baseline for each rate and cost, empty when either side has none."""
	out = {}
	for key in ("connect_rate", "qualified_rate", "cost_per_qualified"):
		a, b = ai[key], baseline[key]
		out[key] = None if a is None or b is None else round(a - b, 2)
	for key in ("site_visits", "complaints"):
		out[key] = ai[key] - baseline[key]
	return out


@sellos_api(COMPANY_ADMIN)
def ai_comparison(from_date=None, to_date=None, baseline_from=None, baseline_to=None):
	"""AI calling against human calling and the human baseline, for any range of dates."""
	start, end = _range(from_date, to_date)
	first, last = _baseline_range(start, baseline_from, baseline_to)
	groups = _groups(start, end, first, last)
	figures = {name: _measures(rows, ai=name == "ai") for name, rows in groups.items()}
	return {
		"from_date": str(start),
		"to_date": str(end),
		"baseline_from": str(first),
		"baseline_to": str(last),
		**figures,
		"difference": _difference(figures["ai"], figures["baseline"]),
	}


@sellos_api(COMPANY_ADMIN)
def ai_comparison_calls(
	group, measure=None, from_date=None, to_date=None, baseline_from=None, baseline_to=None
):
	"""The calls behind one figure: a group (ai, human or baseline) and optionally one of the counted
	measures (connected, qualified, site_visits, handovers, complaints). Nothing about the lead's phone
	number is returned."""
	if group not in GROUPS:
		frappe.throw(_("The group must be ai, human or baseline."))
	if measure not in (None, "") and measure not in MEASURES:
		frappe.throw(_("The measure is not one the comparison counts."))
	start, end = _range(from_date, to_date)
	first, last = _baseline_range(start, baseline_from, baseline_to)
	rows = [r for r in _groups(start, end, first, last)[group] if _measure_matches(r, measure or None)]
	return {
		"group": group,
		"measure": measure or None,
		"calls": [
			{
				"name": r.name,
				"lead": r.lead,
				"mode": "AI" if r.is_ai else "Human",
				"state": r.state,
				"connected": r.connected,
				"outcome": r.outcome,
				"handed_over": bool(r.handover),
				"duration": r.duration or 0,
				"cost": float(r.cost),
				"started_on": str(r.started_on),
			}
			for r in rows
		],
		"totals": _measures(rows, ai=group == "ai"),
	}
