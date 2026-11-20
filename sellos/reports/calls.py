"""The call reports a Company Admin reads (SOS-P2-11): cost by agent and by purpose, connect rate, talk time
and consent coverage, each for a range of dates, and each figure's calls.

Every figure is worked out from one list of Call Logs (`_calls`) and one test (`_matches`). The report adds
the list up and the drill down returns the rows the same test keeps, so a total can never differ from the
Call Log, and a figure and its calls can never differ from each other.

* The date of a call is the date of its `started_on`. The range includes both end days.
* A call is connected when the provider says it completed and it ran for more than 0 seconds. Every
  logged call counts as placed, whatever its state.
* The agent of a call is the agent who clicked to call (SOS-P2-07), or else the lead's owner.
* Cost is the Call Log's rupees, added up exactly (not as floating point numbers).
* Consent coverage is the share of calls whose Consent Check says Consented. The status is read from the
  Consent Check (SOS-P2-04), as the screens do. Consent never blocks a call, here or anywhere.
"""

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN

CONSENT_STATUSES = ("Consented", "Unknown", "Opted out", "Registered DND")
PURPOSES = ("Service", "Transactional", "Promotional")
DEFAULT_DAYS = 30
UNASSIGNED = ""


def _range(from_date, to_date):
	"""The two end days as dates. The default is the last 30 days, ending today."""
	end = getdate(to_date) if to_date else getdate(today())
	start = getdate(from_date) if from_date else add_days(end, -(DEFAULT_DAYS - 1))
	if start > end:
		frappe.throw(_("The start date is after the end date."))
	return start, end


def _calls(start, end):
	"""Every Call Log the reader may read that started between the two days, with the fields the figures use."""
	rows = frappe.get_list(
		"Call Log",
		filters=[
			["started_on", ">=", f"{start} 00:00:00"],
			["started_on", "<", f"{add_days(end, 1)} 00:00:00"],
		],
		fields=[
			"name",
			"lead",
			"agent",
			"purpose",
			"state",
			"duration",
			"cost_rupees",
			"started_on",
			"consent_check",
		],
		order_by="started_on desc, name desc",
		limit_page_length=0,
	)
	statuses = {}
	checks = [r.consent_check for r in rows if r.consent_check]
	if checks:
		statuses = dict(
			frappe.get_all(
				"Consent Check",
				filters={"name": ["in", checks]},
				fields=["name", "consent_status"],
				as_list=True,
			)
		)
	leads = [r.lead for r in rows if r.lead and not r.agent]
	owners = {}
	if leads:
		owners = dict(
			frappe.get_all(
				"Lead", filters={"name": ["in", leads]}, fields=["name", "assigned_to"], as_list=True
			)
		)
	for row in rows:
		row.agent = row.agent or owners.get(row.lead) or UNASSIGNED
		row.connected = row.state == "completed" and (row.duration or 0) > 0
		row.consent_status = statuses.get(row.consent_check) or "Unknown"
		row.cost = Decimal(str(row.cost_rupees or 0))
		row.duration = row.duration or 0
	return rows


def _matches(row, agent=None, purpose=None, connected=None, consent_status=None):
	if agent is not None and row.agent != agent:
		return False
	if purpose is not None and row.purpose != purpose:
		return False
	if connected is not None and row.connected != connected:
		return False
	return consent_status is None or row.consent_status == consent_status


def _figures(rows):
	calls = len(rows)
	connected = sum(1 for r in rows if r.connected)
	return {
		"calls": calls,
		"connected": connected,
		"connect_rate": _percent(connected, calls),
		"talk_seconds": sum(r.duration for r in rows),
		"cost": float(sum((r.cost for r in rows), Decimal(0))),
	}


def _percent(part, whole):
	return round(part * 100 / whole, 1) if whole else 0.0


def _grouped(rows, key):
	groups = defaultdict(list)
	for row in rows:
		groups[row[key]].append(row)
	return groups


@sellos_api(COMPANY_ADMIN)
def call_report(from_date=None, to_date=None):
	"""The four reports for the dates, from the Call Logs the reader may read."""
	start, end = _range(from_date, to_date)
	rows = _calls(start, end)
	names = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}

	by_agent = [
		{
			"agent": agent,
			"agent_name": names.get(agent) or agent or _("No agent"),
			**_figures(group),
		}
		for agent, group in sorted(_grouped(rows, "agent").items())
	]
	by_purpose = [
		{"purpose": purpose, **_figures(group)}
		for purpose, group in sorted(_grouped(rows, "purpose").items())
	]
	by_status = _grouped(rows, "consent_status")
	consent = [
		{
			"status": status,
			"calls": len(by_status.get(status, [])),
			"share": _percent(len(by_status.get(status, [])), len(rows)),
		}
		for status in CONSENT_STATUSES
	]
	total = _figures(rows)
	return {
		"from_date": str(start),
		"to_date": str(end),
		"totals": {**total, "consent_coverage": _percent(len(by_status.get("Consented", [])), len(rows))},
		"by_agent": by_agent,
		"by_purpose": by_purpose,
		"consent": consent,
	}


def _flag(value):
	"""A query value for connected: "1" or "0" (or a real boolean), and None when it is not given."""
	if value in (None, ""):
		return None
	return str(value).lower() in ("1", "true")


@sellos_api(COMPANY_ADMIN)
def call_report_calls(
	from_date=None, to_date=None, agent=None, purpose=None, connected=None, consent_status=None
):
	"""The calls behind one figure. The filters are the ones the report groups by. An empty `agent` is the
	calls with no agent. Each row is one Call Log; nothing about the lead's phone number is returned."""
	start, end = _range(from_date, to_date)
	if purpose is not None and purpose not in PURPOSES:
		frappe.throw(_("The purpose must be Service, Transactional or Promotional."))
	if consent_status is not None and consent_status not in CONSENT_STATUSES:
		frappe.throw(_("The consent status is not one of the four statuses."))
	keep = [r for r in _calls(start, end) if _matches(r, agent, purpose, _flag(connected), consent_status)]
	names = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	return {
		"from_date": str(start),
		"to_date": str(end),
		"calls": [
			{
				"name": r.name,
				"lead": r.lead,
				"agent": r.agent,
				"agent_name": names.get(r.agent) or r.agent or _("No agent"),
				"purpose": r.purpose,
				"state": r.state,
				"connected": r.connected,
				"duration": r.duration,
				"cost": float(r.cost),
				"started_on": str(r.started_on),
				"consent_status": r.consent_status,
			}
			for r in keep
		],
		"totals": _figures(keep),
	}
