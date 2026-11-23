"""The Company Admin's business reports that count more than one thing (SOS-P5-02).

The reports that group one kind of record by one field are Report Definitions on the engine
(`sellos.reports.engine`). These four read several records at once and so are methods of their own. Each
filters by date the way the engine does (`engine._range`, both end days included, the last 30 days by
default) and reads through `frappe.get_list` as the reader, and each figure is one count of the records the
same query lists, so every figure can be reconciled with the raw tables.

* **Lead funnel.** The leads created in the dates, by stage. A lead has *reached* a stage when the stage it
  is in now, or any stage in its stage log, is that stage or a later one of the same pipeline that is not a
  Lost stage. *Conversion* is the share of the leads that reached the stage; a lead is *won* when it is in a
  Won stage now.
* **Source performance.** The same leads by source: leads, won, lost and the conversion to won.
* **Agent productivity.** Per agent, in the dates: leads created, calls and connected calls (completed and
  more than 0 seconds), talk seconds, site visits done, follow ups done and deals booked.
* **Listing and mandate ageing.** Listings by the age of the listing and mandates by the age of the mandate
  in days on the last day of the dates, in four bands. Only listings created, and mandates started, in the
  dates are counted. A signed mandate is also *expired* when its term has run out on that day.

No figure holds a phone number. A rupee total is added up exactly, not as floating point numbers.
"""

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_days, add_months, date_diff, getdate

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.reports.engine import _people, _range

BANDS = (
	("0 to 30 days", 0, 30),
	("31 to 60 days", 31, 60),
	("61 to 90 days", 61, 90),
	("Over 90 days", 91, None),
)
PIPELINE = "Buyer"


def _day_filters(field, start, end):
	return [[field, ">=", f"{start} 00:00:00"], [field, "<", f"{add_days(end, 1)} 00:00:00"]]


def _percent(part, whole):
	return round(part * 100 / whole, 1) if whole else 0.0


def _leads(start, end):
	return frappe.get_list(
		"Lead",
		filters=[["archived", "=", 0], ["pipeline", "=", PIPELINE], *_day_filters("creation", start, end)],
		fields=["name", "stage", "source", "assigned_to"],
		limit_page_length=0,
	)


def _stages() -> dict:
	"""{name: (position, type)} for the stages of the buyer pipeline."""
	return {
		s.name: (s.position or 0, s.stage_type)
		for s in frappe.get_all(
			"Pipeline Stage", filters={"pipeline": PIPELINE}, fields=["name", "position", "stage_type"]
		)
	}


def _reached(leads, stages) -> dict:
	"""{lead: set of stages it has been in}, from its stage now and its stage log."""
	names = [lead.name for lead in leads]
	seen = defaultdict(set)
	for lead in leads:
		if lead.stage:
			seen[lead.name].add(lead.stage)
	if names:
		for row in frappe.get_all(
			"Lead Stage Change",
			filters={"parenttype": "Lead", "parent": ["in", names]},
			fields=["parent", "to_stage"],
			limit_page_length=0,
		):
			if row.to_stage:
				seen[row.parent].add(row.to_stage)
	return seen


def _in_funnel(stages, name) -> bool:
	"""The stages up to the Lost stage make the funnel. A stage after it (Nurture) is a side stage that no
	lead advances through, and a Lost stage is where a lead leaves."""
	lost_at = min((p for p, kind in stages.values() if kind == "Lost"), default=None)
	position, kind = stages[name]
	return kind != "Lost" and (lost_at is None or position < lost_at)


def _passed(history, stages, position) -> bool:
	return any(_in_funnel(stages, s) and stages[s][0] >= position for s in history if s in stages)


def _kinds(leads, stages) -> tuple[int, int]:
	won = sum(1 for lead in leads if stages.get(lead.stage, (0, ""))[1] == "Won")
	lost = sum(1 for lead in leads if stages.get(lead.stage, (0, ""))[1] == "Lost")
	return won, lost


@sellos_api(COMPANY_ADMIN)
def lead_funnel(from_date=None, to_date=None):
	"""The leads created in the dates by stage: how many are in it now, how many reached it, and the share."""
	start, end = _range(from_date, to_date)
	leads = _leads(start, end)
	stages = _stages()
	seen = _reached(leads, stages)
	now = defaultdict(int)
	for lead in leads:
		now[lead.stage or ""] += 1
	rows = []
	previous = None
	for name, (position, kind) in sorted(stages.items(), key=lambda item: (item[1][0], item[0])):
		if not _in_funnel(stages, name):
			reached = None
		else:
			reached = sum(1 for lead in leads if _passed(seen[lead.name], stages, position))
		rows.append(
			{
				"stage": name,
				"type": kind,
				"in_stage": now.get(name, 0),
				"reached": reached,
				"conversion": _percent(reached, len(leads)) if reached is not None else None,
				"step_conversion": _percent(reached, previous) if reached is not None and previous else None,
			}
		)
		if reached is not None:
			previous = reached
	won, lost = _kinds(leads, stages)
	return {
		"from_date": str(start),
		"to_date": str(end),
		"totals": {"leads": len(leads), "won": won, "lost": lost, "conversion": _percent(won, len(leads))},
		"rows": rows,
	}


@sellos_api(COMPANY_ADMIN)
def source_performance(from_date=None, to_date=None):
	"""The leads created in the dates by source: leads, won, lost and the conversion to won."""
	start, end = _range(from_date, to_date)
	leads = _leads(start, end)
	stages = _stages()
	groups = defaultdict(list)
	for lead in leads:
		groups[lead.source or ""].append(lead)
	rows = []
	for source, group in groups.items():
		won, lost = _kinds(group, stages)
		rows.append(
			{
				"source": source,
				"label": source or _("Not set"),
				"leads": len(group),
				"won": won,
				"lost": lost,
				"conversion": _percent(won, len(group)),
			}
		)
	rows.sort(key=lambda r: (-r["leads"], r["label"]))
	won, lost = _kinds(leads, stages)
	return {
		"from_date": str(start),
		"to_date": str(end),
		"totals": {"leads": len(leads), "won": won, "lost": lost, "conversion": _percent(won, len(leads))},
		"rows": rows,
	}


def _by_agent(doctype, field, start, end, date_field, filters, date_is_datetime=True):
	"""The unarchived records of the doctype in the dates (with their agent field) that pass the filters."""
	window = (
		_day_filters(date_field, start, end) if date_is_datetime else [[date_field, "between", [start, end]]]
	)
	return frappe.get_list(
		doctype,
		filters=[["archived", "=", 0], *window, *filters],
		fields=["name", field],
		limit_page_length=0,
	)


@sellos_api(COMPANY_ADMIN)
def agent_productivity(from_date=None, to_date=None):
	"""One row per agent with work in the dates. A call with no agent counts for its lead's owner, as in the
	call reports (SOS-P2-11)."""
	start, end = _range(from_date, to_date)
	people = _people()
	table = defaultdict(
		lambda: {
			"leads": 0,
			"calls": 0,
			"connected": 0,
			"talk_seconds": 0,
			"visits_done": 0,
			"follow_ups_done": 0,
			"deals": 0,
		}
	)
	for lead in _leads(start, end):
		table[lead.assigned_to or ""]["leads"] += 1
	calls = frappe.get_list(
		"Call Log",
		filters=_day_filters("started_on", start, end),
		fields=["name", "agent", "lead", "state", "duration"],
		limit_page_length=0,
	)
	owners = {}
	missing = [c.lead for c in calls if c.lead and not c.agent]
	if missing:
		owners = dict(
			frappe.get_all(
				"Lead", filters={"name": ["in", missing]}, fields=["name", "assigned_to"], as_list=True
			)
		)
	for call in calls:
		row = table[call.agent or owners.get(call.lead) or ""]
		row["calls"] += 1
		row["talk_seconds"] += call.duration or 0
		row["connected"] += int(call.state == "completed" and (call.duration or 0) > 0)
	for visit in _by_agent("Site Visit", "agent", start, end, "visit_datetime", [["status", "=", "Done"]]):
		table[visit.agent or ""]["visits_done"] += 1
	for task in _by_agent(
		"Lead Task", "assigned_to", start, end, "due_date", [["status", "=", "Done"]], date_is_datetime=False
	):
		table[task.assigned_to or ""]["follow_ups_done"] += 1
	for deal in _by_agent(
		"Deal",
		"booked_by",
		start,
		end,
		"deal_date",
		[["deal_status", "!=", "Cancelled"]],
		date_is_datetime=False,
	):
		table[deal.booked_by or ""]["deals"] += 1
	rows = [
		{
			"agent": agent,
			"agent_name": people.get(agent) or agent or _("No agent"),
			**figures,
			"connect_rate": _percent(figures["connected"], figures["calls"]),
		}
		for agent, figures in table.items()
	]
	rows.sort(key=lambda r: (-r["leads"], r["agent_name"]))
	keys = ("leads", "calls", "connected", "talk_seconds", "visits_done", "follow_ups_done", "deals")
	return {
		"from_date": str(start),
		"to_date": str(end),
		"rows": rows,
		"totals": {key: sum(r[key] for r in rows) for key in keys},
	}


def _band(days):
	for label, low, high in BANDS:
		if days >= low and (high is None or days <= high):
			return label
	return BANDS[0][0]


@sellos_api(COMPANY_ADMIN)
def ageing_report(from_date=None, to_date=None):
	"""Listings and mandates in the dates by their age in days on the last day, in four bands."""
	start, end = _range(from_date, to_date)
	listings = frappe.get_list(
		"Listing",
		filters=[["archived", "=", 0], *_day_filters("creation", start, end)],
		fields=["name", "creation", "published", "asking_price"],
		limit_page_length=0,
	)
	mandates = frappe.get_list(
		"Mandate",
		filters=[["archived", "=", 0], ["start_date", "between", [start, end]]],
		fields=["name", "start_date", "status", "term_months"],
		limit_page_length=0,
	)
	listing_bands = {label: {"count": 0, "published": 0, "asking": Decimal(0)} for label, _l, _h in BANDS}
	for row in listings:
		cell = listing_bands[_band(date_diff(end, getdate(row.creation)))]
		cell["count"] += 1
		cell["published"] += int(bool(row.published))
		cell["asking"] += Decimal(str(row.asking_price or 0))
	mandate_bands = {label: {"count": 0, "signed": 0, "expired": 0} for label, _l, _h in BANDS}
	for row in mandates:
		cell = mandate_bands[_band(date_diff(end, getdate(row.start_date)))]
		cell["count"] += 1
		if row.status == "Signed":
			cell["signed"] += 1
			if row.term_months and add_months(getdate(row.start_date), row.term_months) < end:
				cell["expired"] += 1
	return {
		"from_date": str(start),
		"to_date": str(end),
		"listings": {
			"total": len(listings),
			"bands": [
				{
					"band": label,
					"count": cell["count"],
					"published": cell["published"],
					"asking": float(cell["asking"].quantize(Decimal("0.01"))),
				}
				for label, cell in listing_bands.items()
			],
		},
		"mandates": {
			"total": len(mandates),
			"bands": [{"band": label, **cell} for label, cell in mandate_bands.items()],
		},
	}
