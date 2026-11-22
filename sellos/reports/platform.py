"""The Platform Admin's reports (SOS-P5-03): companies, usage and calling spend, as totals per company.

These reports hold no lead, client or call record and no phone number. The Platform Admin sees no company
CRM data by role (CLAUDE.md), so nothing here reads a Lead, Client, Call Log or Lead Activity of any
company. What the control site holds per company is one Company Usage row per month: four counts and one
sum of rupees, made by each company's own site (`company_totals`, which reads only that site's tables and
returns numbers) and stored by `record_usage`, which refuses anything else.

* **Companies.** Every company on the platform with its status and plan.
* **Usage.** Per company: users (as of the latest month in the dates), and the new leads, calls and talk
  time of the months in the dates.
* **Calling spend.** Per company: the calls and what they cost, exact to the paisa.
* **Revenue, churn and failed payments.** Panels that wait for billing (see `panels.py`).

The dates choose whole months: a month that has any day in the range counts in full, because a company's
usage is stored per month. The default range is the last 30 days, as in the other reports.
"""

from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_days, get_first_day, get_last_day, getdate, now_datetime, today

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, PLATFORM_ADMIN, SALES_MANAGER
from sellos.reports.engine import _range
from sellos.reports.panels import reader, run_panel

USAGE = "Company Usage"
TENANT = "Tenant"
COUNT_FIELDS = ("users", "leads", "calls", "call_seconds")
COST_FIELD = "call_cost"
TOTAL_FIELDS = (*COUNT_FIELDS, COST_FIELD)
# The people who work for the company and count as its users. A client or a partner is not a seat.
STAFF_ROLES = (COMPANY_ADMIN, SALES_MANAGER, AGENT)
CENT = Decimal("0.01")

REPORTS = (
	{
		"key": "companies",
		"title": "Companies",
		"description": "Every company on the platform, with its status and plan.",
		"dated": False,
	},
	{
		"key": "usage",
		"title": "Usage",
		"description": "Users, new leads, calls and talk time of each company, by month.",
		"dated": True,
	},
	{
		"key": "calling-spend",
		"title": "Calling spend",
		"description": "The calls each company made and what they cost, by month.",
		"dated": True,
	},
)
PANELS = (
	{
		"key": "revenue",
		"title": "Revenue",
		"description": "What the companies paid in the dates.",
		"reader": "sellos.billing.report_panels.revenue",
		"waiting": "Revenue will appear here once billing is live.",
	},
	{
		"key": "churn",
		"title": "Churn",
		"description": "The companies that cancelled in the dates.",
		"reader": "sellos.billing.report_panels.churn",
		"waiting": "Churn will appear here once billing is live.",
	},
	{
		"key": "failed-payments",
		"title": "Failed payments",
		"description": "The payments that failed in the dates, by company.",
		"reader": "sellos.billing.report_panels.failed_payments",
		"waiting": "Failed payments will appear here once billing is live.",
	},
)


# ---- what a company's own site reports and the control site stores -----------------------------------


def company_totals(month=None) -> dict:
	"""The totals of one month on THIS site, which is one company's: its staff users, the leads created,
	and the calls started with their talk time and cost. Four numbers and a sum, and nothing else leaves."""
	first = get_first_day(month or today())
	begin, stop = f"{first} 00:00:00", f"{add_days(get_last_day(first), 1)} 00:00:00"
	users = frappe.db.sql(
		"""select count(distinct u.name) from `tabUser` u
		join `tabHas Role` r on r.parent = u.name and r.parenttype = 'User'
		where u.enabled = 1 and u.name not in ('Administrator', 'Guest') and r.role in %(roles)s""",
		{"roles": STAFF_ROLES},
	)[0][0]
	leads = frappe.db.sql(
		"select count(*) from `tabLead` where creation >= %s and creation < %s", (begin, stop)
	)[0][0]
	calls, seconds, cost = frappe.db.sql(
		"""select count(*), coalesce(sum(duration), 0), coalesce(sum(cost_rupees), 0)
		from `tabCall Log` where started_on >= %s and started_on < %s""",
		(begin, stop),
	)[0]
	return {
		"month": str(first),
		"users": int(users),
		"leads": int(leads),
		"calls": int(calls),
		"call_seconds": int(seconds),
		"call_cost": float(Decimal(str(cost)).quantize(CENT)),
	}


def _number(field, value):
	if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
		frappe.throw(_("{0} must be a number.").format(field))
	try:
		number = Decimal(str(value))
	except ArithmeticError:
		frappe.throw(_("{0} must be a number.").format(field))
	if not number.is_finite() or number < 0:
		frappe.throw(_("{0} must be a number of zero or more.").format(field))
	if field == COST_FIELD:
		return number.quantize(CENT)
	if number != number.to_integral_value():
		frappe.throw(_("{0} must be a whole number.").format(field))
	return int(number)


def record_usage(tenant, totals) -> str:
	"""Store one month's totals of one company on the control site, replacing what was stored for that
	company and month. `totals` may hold the month and the five numbers, and nothing else: any other key is
	refused, so a lead or a phone number cannot be carried in. Returns the row's name."""
	if not tenant or not frappe.db.exists(TENANT, tenant):
		frappe.throw(_("This company does not exist."), frappe.DoesNotExistError)
	totals = dict(totals or {})
	month = get_first_day(totals.pop("month", None) or today())
	unknown = set(totals) - set(TOTAL_FIELDS)
	if unknown:
		frappe.throw(_("Usage holds only totals. It cannot hold {0}.").format(", ".join(sorted(unknown))))
	values = {field: _number(field, totals.get(field, 0)) for field in TOTAL_FIELDS}
	values[COST_FIELD] = float(values[COST_FIELD])
	name = frappe.db.get_value(USAGE, {"tenant": tenant, "period_start": month})
	doc = frappe.get_doc(USAGE, name) if name else frappe.new_doc(USAGE)
	doc.update({"tenant": tenant, "period_start": month, "recorded_on": now_datetime(), **values})
	doc.save(ignore_permissions=True)
	return doc.name


# ---- the reports ------------------------------------------------------------------------------------


def _head(defn) -> dict:
	return {k: defn[k] for k in ("key", "title", "description", "dated")}


def _column(field, label, unit="number"):
	return {"field": field, "label": label, "unit": unit}


def _rupees(value: Decimal) -> float:
	return float(value.quantize(CENT))


def _companies() -> list[dict]:
	return frappe.get_all(
		TENANT,
		fields=["name", "company_name", "status", "plan", "creation"],
		order_by="company_name asc, name asc",
		limit_page_length=0,
	)


def _months(first, last) -> dict:
	"""{tenant: [Company Usage rows, oldest month first]} for the months from `first` to `last`."""
	found = {}
	for row in frappe.get_all(
		USAGE,
		filters={"period_start": ["between", [first, last]]},
		fields=["tenant", "period_start", *TOTAL_FIELDS],
		order_by="period_start asc",
		limit_page_length=0,
	):
		found.setdefault(row.tenant, []).append(row)
	return found


def _companies_report() -> dict:
	rows = _companies()
	by_status = {}
	for row in rows:
		by_status[row.status] = by_status.get(row.status, 0) + 1
	return {
		"columns": [_column("status", "Status", "text"), _column("plan", "Plan", "text")],
		"rows": [
			{"key": r.name, "label": r.company_name, "values": [r.status or "", r.plan or ""]} for r in rows
		],
		"stats": [
			{"label": _("Companies"), "value": len(rows), "unit": "number"},
			{"label": _("Active"), "value": by_status.get("Active", 0), "unit": "number"},
		],
	}


def _usage_report(first, last) -> dict:
	months = _months(first, last)
	rows, sums = [], dict.fromkeys(("users", "leads", "calls", "call_seconds"), 0)
	for company in _companies():
		held = months.get(company.name, [])
		# Users are a level, not a flow: the latest month in the dates, never a sum of months.
		users = held[-1].users if held else 0
		leads, calls, seconds = (sum(r[f] for r in held) for f in ("leads", "calls", "call_seconds"))
		rows.append(
			{"key": company.name, "label": company.company_name, "values": [users, leads, calls, seconds]}
		)
		for field, value in zip(sums, (users, leads, calls, seconds), strict=True):
			sums[field] += value
	return {
		"columns": [
			_column("users", "Users"),
			_column("leads", "New leads"),
			_column("calls", "Calls"),
			_column("call_seconds", "Talk time", "seconds"),
		],
		"rows": rows,
		"stats": [
			{"label": _("Users"), "value": sums["users"], "unit": "number"},
			{"label": _("New leads"), "value": sums["leads"], "unit": "number"},
			{"label": _("Calls"), "value": sums["calls"], "unit": "number"},
		],
	}


def _spend_report(first, last) -> dict:
	months = _months(first, last)
	rows, calls_all, cost_all = [], 0, Decimal(0)
	for company in _companies():
		held = months.get(company.name, [])
		calls = sum(r.calls for r in held)
		cost = sum((Decimal(str(r.call_cost or 0)) for r in held), Decimal(0))
		rows.append({"key": company.name, "label": company.company_name, "values": [calls, _rupees(cost)]})
		calls_all += calls
		cost_all += cost
	return {
		"columns": [_column("calls", "Calls"), _column("call_cost", "Calling spend", "rupees")],
		"rows": rows,
		"stats": [
			{"label": _("Calls"), "value": calls_all, "unit": "number"},
			{"label": _("Calling spend"), "value": _rupees(cost_all), "unit": "rupees"},
		],
	}


def _report(key):
	for defn in REPORTS:
		if defn["key"] == key:
			return defn
	frappe.throw(_("This report does not exist."), frappe.DoesNotExistError)


@sellos_api(PLATFORM_ADMIN)
def list_platform_reports():
	"""The reports, and the billing panels with whether billing has switched them on."""
	return {
		"reports": [_head(defn) for defn in REPORTS],
		"panels": [
			{"key": p["key"], "title": p["title"], "available": reader(p["reader"]) is not None}
			for p in PANELS
		],
	}


@sellos_api(PLATFORM_ADMIN)
def run_platform_report(report, from_date=None, to_date=None):
	"""One report as totals per company, for a range of dates, with the billing panels beside it."""
	defn = _report(report)
	start, end = _range(from_date, to_date)
	first, last = get_first_day(start), getdate(end)
	if defn["key"] == "companies":
		body = _companies_report()
	elif defn["key"] == "usage":
		body = _usage_report(first, last)
	else:
		body = _spend_report(first, last)
	return {
		"report": _head(defn),
		"from_date": str(start),
		"to_date": str(end),
		"first_month": str(first),
		"last_month": str(get_first_day(last)),
		**body,
		"panels": [run_panel(panel, start, end) for panel in PANELS],
	}
