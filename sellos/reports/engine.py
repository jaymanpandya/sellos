"""The report engine (SOS-P5-01). Every report is a Report Definition: the records it counts (one of the
sources in `sellos.reports.sources`), the field it groups by, whether it counts or adds up a field, fixed
filters, and which roles read it. The engine shares what every report needs:

* **Filters.** A range of dates (both end days included, the last 30 days by default) and, for a reader who
  may see more than their own records, one agent.
* **Role scope.** A Company Admin reads every record. A Sales Manager reads its own team's and an Agent its
  own, because the rows are read through `frappe.get_list`, which applies the same rules as the lead
  screens. The engine adds no rule of its own, so a report can never show what a screen would hide.
* **Drill down.** `report_records` lists the records behind a figure with the same filters, so a figure and
  its records come from one query and can never differ.
* **Summary tables.** Every night `refresh_all_summaries` rebuilds, per definition, one Report Summary row
  per day and group, for every day before today. A Company Admin's figures for those days are added up from
  the table, and the days since (today, or a night that was missed) are read from the records. A reader with
  a narrower scope, and any report filtered by agent, reads the records, so scope is never lost to a table.
  A change to a record of an earlier day shows in the table at the next refresh.

Money is added up exactly (not as floating point numbers). No figure and no record holds a phone number.
"""

import json
import re
from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime, today

from sellos.access.lead_permissions import scope_for
from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.reports.sources import SOURCES

DEFINITION = "Report Definition"
SUMMARY = "Report Summary"
DEFAULT_DAYS = 30
MAX_RECORDS = 200
KEY_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# What a change to makes the stored summary wrong.
CONFIG_FIELDS = ("source_doctype", "group_by", "measure", "measure_field", "filters")
EDITABLE = (
	"title",
	"description",
	"enabled",
	"source_doctype",
	"group_by",
	"measure",
	"measure_field",
	"filters",
	"visible_to_sales_manager",
	"visible_to_agent",
)
_ALL = object()

# The reports every company starts with. A company's own changes to one are never overwritten.
DEFAULT_DEFINITIONS = (
	{
		"report_key": "leads-by-stage",
		"title": "Leads by stage",
		"description": "New leads in the dates, by the stage they are in now.",
		"source_doctype": "Lead",
		"group_by": "stage",
		"visible_to_sales_manager": 1,
		"visible_to_agent": 1,
	},
	{
		"report_key": "leads-by-source",
		"title": "Leads by source",
		"description": "New leads in the dates, by where they came from.",
		"source_doctype": "Lead",
		"group_by": "source",
		"visible_to_sales_manager": 1,
		"visible_to_agent": 0,
	},
	{
		"report_key": "site-visits-by-status",
		"title": "Site visits by status",
		"description": "Site visits in the dates, by status.",
		"source_doctype": "Site Visit",
		"group_by": "status",
		"visible_to_sales_manager": 1,
		"visible_to_agent": 1,
	},
	{
		"report_key": "follow-ups-by-status",
		"title": "Follow ups by status",
		"description": "Follow ups due in the dates, by status.",
		"source_doctype": "Lead Task",
		"group_by": "status",
		"visible_to_sales_manager": 1,
		"visible_to_agent": 1,
	},
	{
		"report_key": "call-cost-by-purpose",
		"title": "Call cost by purpose",
		"description": "What the calls started in the dates cost, by purpose.",
		"source_doctype": "Call Log",
		"group_by": "purpose",
		"measure": "Sum",
		"measure_field": "cost_rupees",
		"visible_to_sales_manager": 1,
		"visible_to_agent": 0,
	},
)


def ensure_default_definitions() -> list[str]:
	"""Make any default report that is missing. Safe to run again: an existing report is left as it is."""
	made = []
	for values in DEFAULT_DEFINITIONS:
		if not frappe.db.exists(DEFINITION, values["report_key"]):
			frappe.get_doc({"doctype": DEFINITION, **values}).insert(ignore_permissions=True)
			made.append(values["report_key"])
	return made


# ---- the definition ---------------------------------------------------------------------------------


def parse_filters(raw) -> dict:
	"""The fixed filters as a dict. Empty is none. Anything but a JSON object of text and numbers is refused."""
	if raw in (None, "", {}):
		return {}
	try:
		value = json.loads(raw) if isinstance(raw, str) else raw
	except ValueError:
		value = None
	if not isinstance(value, dict) or not all(
		isinstance(v, str | int | float) and not isinstance(v, bool) for v in value.values()
	):
		frappe.throw(_("The fixed filters must be a JSON object of field and value pairs."))
	return value


def validate_definition(doc):
	"""The configuration of a Report Definition is checked against what the source allows (sources.py)."""
	if not KEY_PATTERN.match(doc.report_key or ""):
		frappe.throw(_("The key may hold only lower case letters, digits and hyphens."))
	source = SOURCES.get(doc.source_doctype)
	if not source:
		frappe.throw(_("The records must be leads, calls, site visits or follow ups."))
	if doc.group_by and doc.group_by not in source["groups"]:
		frappe.throw(_("{0} cannot be grouped by {1}.").format(doc.source_doctype, doc.group_by))
	if doc.measure == "Sum":
		if doc.measure_field not in source["sums"]:
			frappe.throw(_("{0} cannot add up {1}.").format(doc.source_doctype, doc.measure_field))
	else:
		doc.measure_field = None
	filters = parse_filters(doc.filters)
	allowed = set(source["groups"]) | {source["scope_field"]}
	for field in filters:
		if field not in allowed:
			frappe.throw(_("{0} cannot be filtered by {1}.").format(doc.source_doctype, field))
	doc.filters = json.dumps(filters, sort_keys=True) if filters else None
	if not doc.is_new() and any(doc.has_value_changed(f) for f in CONFIG_FIELDS):
		# The stored rows were made for the old configuration.
		frappe.db.delete(SUMMARY, {"report": doc.name})
		doc.summarised_to = None
		doc.last_refreshed = None


def _definition(report) -> "frappe.model.document.Document":
	if not report or not frappe.db.exists(DEFINITION, report):
		frappe.throw(_("This report does not exist."), frappe.DoesNotExistError)
	return frappe.get_doc(DEFINITION, report)


def _reads(defn, roles) -> bool:
	"""May a user with these roles read the report? The Company Admin reads every enabled report."""
	if not defn.enabled:
		return False
	if COMPANY_ADMIN in roles:
		return True
	return bool(
		(SALES_MANAGER in roles and defn.visible_to_sales_manager)
		or (AGENT in roles and defn.visible_to_agent)
	)


def _readable(report):
	defn = _definition(report)
	if not _reads(defn, frappe.get_roles()):
		frappe.throw(_("You cannot read this report."), frappe.PermissionError)
	return defn


def _describe(defn) -> dict:
	source = SOURCES[defn.source_doctype]
	if defn.measure == "Sum":
		label, unit = source["sums"][defn.measure_field]
	else:
		label, unit = _("Records"), "number"
	return {
		"key": defn.name,
		"title": defn.title,
		"description": defn.description or "",
		"source_doctype": defn.source_doctype,
		"group_by": defn.group_by or "",
		"group_label": source["groups"].get(defn.group_by) or _("All"),
		"measure": defn.measure,
		"measure_label": label,
		"unit": unit,
		"date_label": source["date_label"],
		"enabled": bool(defn.enabled),
		"summarised_to": str(defn.summarised_to) if defn.summarised_to else None,
		"last_refreshed": str(defn.last_refreshed) if defn.last_refreshed else None,
	}


# ---- reading the records ----------------------------------------------------------------------------


def _range(from_date, to_date):
	"""The two end days as dates. The default is the last 30 days, ending today."""
	end = getdate(to_date) if to_date else getdate(today())
	start = getdate(from_date) if from_date else add_days(end, -(DEFAULT_DAYS - 1))
	if start > end:
		frappe.throw(_("The start date is after the end date."))
	return start, end


def _filters(defn, start, end, group=_ALL, agent=None):
	source = SOURCES[defn.source_doctype]
	field = source["date_field"]
	filters = [[k, "=", v] for k, v in source["base_filters"].items()]
	filters += [[k, "=", v] for k, v in parse_filters(defn.filters).items()]
	if start is not None and end is not None and source["date_type"] == "Date":
		filters.append([field, "between", [start, end]])
	else:
		if start is not None:
			filters.append([field, ">=", f"{start} 00:00:00"])
		if end is not None:
			filters.append([field, "<", f"{add_days(end, 1)} 00:00:00"])
	if agent is not None:
		filters.append(
			[source["scope_field"], "=", agent] if agent else [source["scope_field"], "is", "not set"]
		)
	if group is not _ALL and defn.group_by:
		filters.append([defn.group_by, "=", group] if group else [defn.group_by, "is", "not set"])
	return filters


def _fetch(defn, start, end, group=_ALL, agent=None, columns=None, ignore_permissions=False):
	"""The records of the report between the two days, read as the current user (so with that user's scope)."""
	source = SOURCES[defn.source_doctype]
	fields = {"name", source["date_field"]}
	fields.update(columns or ())
	if defn.group_by:
		fields.add(defn.group_by)
	if defn.measure == "Sum":
		fields.add(defn.measure_field)
	return frappe.get_list(
		defn.source_doctype,
		filters=_filters(defn, start, end, group, agent),
		fields=sorted(fields),
		order_by=f"{source['date_field']} desc, name desc",
		limit_page_length=0,
		ignore_permissions=ignore_permissions,
	)


def _amount(defn, row) -> Decimal:
	if defn.measure != "Sum":
		return Decimal(0)
	return Decimal(str(row.get(defn.measure_field) or 0))


def _fold(defn, rows) -> dict:
	"""{(day, group): [records, total]} for the rows."""
	source = SOURCES[defn.source_doctype]
	days = defaultdict(lambda: [0, Decimal(0)])
	for row in rows:
		cell = days[
			(getdate(row[source["date_field"]]), str(row.get(defn.group_by) or "") if defn.group_by else "")
		]
		cell[0] += 1
		cell[1] += _amount(defn, row)
	return days


def _people() -> dict:
	return {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}


def _figures(defn, start, end, agent) -> dict:
	"""{group: [records, total]} for the dates. A Company Admin's days that the summary table holds are added
	up from it and the rest are read from the records."""
	figures = defaultdict(lambda: [0, Decimal(0)])
	live_start = start
	wide = scope_for(frappe.get_roles()) == "all"
	if wide and agent is None and defn.summarised_to:
		stored_end = min(end, getdate(defn.summarised_to))
		if start <= stored_end:
			for row in frappe.get_all(
				SUMMARY,
				filters={"report": defn.name, "summary_date": ["between", [start, stored_end]]},
				fields=["group_value", "record_count", "total"],
				limit_page_length=0,
			):
				figures[row.group_value or ""][0] += row.record_count
				figures[row.group_value or ""][1] += Decimal(str(row.total or 0))
			live_start = add_days(stored_end, 1)
	if live_start <= end:
		for (_day, group), (count, total) in _fold(defn, _fetch(defn, live_start, end, agent=agent)).items():
			figures[group][0] += count
			figures[group][1] += total
	return figures


def _label(defn, group, people) -> str:
	if not group:
		return _("Not set") if defn.group_by else _("All")
	if defn.group_by in SOURCES[defn.source_doctype]["users"]:
		return people.get(group) or group
	return group


def _total(defn, value: Decimal):
	if defn.measure != "Sum":
		return None
	return float(value.quantize(Decimal("0.01")))


def run_report_figures(defn, start, end, agent=None) -> dict:
	people = _people()
	figures = _figures(defn, start, end, agent)
	rows = [
		{"group": group, "label": _label(defn, group, people), "count": count, "total": _total(defn, total)}
		for group, (count, total) in figures.items()
		if count
	]
	rows.sort(key=lambda r: (-r["count"], r["label"]))
	return {
		"rows": rows,
		"totals": {
			"count": sum(r["count"] for r in rows),
			"total": _total(defn, sum((t for _c, t in figures.values()), Decimal(0))),
		},
	}


def _scope_name() -> str:
	return scope_for(frappe.get_roles())


def _agent_argument(agent):
	return None if agent in (None, "null") else str(agent)


# ---- the summary table ------------------------------------------------------------------------------


def refresh_summary(name) -> dict:
	"""Rebuild the summary rows of one report for every day before today. The rows of the old build go in
	the same transaction, so a reader never sees half a table."""
	defn = _definition(name)
	through = add_days(getdate(today()), -1)
	folded = _fold(defn, _fetch(defn, None, through, ignore_permissions=True))
	now = now_datetime()
	owner = "Administrator"
	frappe.db.delete(SUMMARY, {"report": name})
	values = [
		(frappe.generate_hash(length=12), now, now, owner, owner, name, day, group, count, float(total))
		for (day, group), (count, total) in sorted(folded.items(), key=lambda item: (item[0][0], item[0][1]))
	]
	if values:
		frappe.db.bulk_insert(
			SUMMARY,
			fields=[
				"name",
				"creation",
				"modified",
				"modified_by",
				"owner",
				"report",
				"summary_date",
				"group_value",
				"record_count",
				"total",
			],
			values=values,
		)
	frappe.db.set_value(
		DEFINITION, name, {"summarised_to": through, "last_refreshed": now}, update_modified=False
	)
	return {"report": name, "rows": len(values), "summarised_to": str(through)}


def refresh_all_summaries() -> list[dict]:
	"""The nightly job (scheduler event `daily`). A report that fails is logged and the others go on."""
	done = []
	for name in frappe.get_all(DEFINITION, filters={"enabled": 1}, pluck="name"):
		point = f"summary_{frappe.generate_hash(length=8)}"
		frappe.db.savepoint(point)
		try:
			done.append(refresh_summary(name))
		except Exception:
			# Only this report's table goes back. The scheduler commits the others when the job ends.
			frappe.db.rollback(save_point=point)
			frappe.log_error(title=f"SOS-P5-01 summary refresh failed for {name}")
	return done


# ---- the API ----------------------------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN, SALES_MANAGER, AGENT)
def list_reports():
	"""The reports the reader may open. A Company Admin also sees the disabled ones."""
	roles = frappe.get_roles()
	admin = COMPANY_ADMIN in roles
	reports = []
	for name in frappe.get_all(DEFINITION, pluck="name", order_by="title asc"):
		defn = frappe.get_doc(DEFINITION, name)
		if admin or _reads(defn, roles):
			reports.append(_describe(defn))
	return {"reports": reports, "scope": _scope_name()}


@sellos_api(COMPANY_ADMIN, SALES_MANAGER, AGENT)
def run_report(report, from_date=None, to_date=None, agent=None):
	"""The figures of one report for a range of dates, from the records the reader may see."""
	defn = _readable(report)
	start, end = _range(from_date, to_date)
	return {
		"report": _describe(defn),
		"from_date": str(start),
		"to_date": str(end),
		"scope": _scope_name(),
		**run_report_figures(defn, start, end, _agent_argument(agent)),
	}


@sellos_api(COMPANY_ADMIN, SALES_MANAGER, AGENT)
def report_records(report, from_date=None, to_date=None, group=None, agent=None):
	"""The records behind a figure, newest first: the group's (an empty `group` is the records with no
	value), or every record in the dates when no group is given. At most 200 are listed; `total` is the
	number of records, which is the figure's number."""
	defn = _readable(report)
	source = SOURCES[defn.source_doctype]
	start, end = _range(from_date, to_date)
	columns = [field for field, _label in source["columns"]]
	lead_field = source["lead_field"]
	rows = _fetch(
		defn,
		start,
		end,
		group=_ALL if group is None else str(group),
		agent=_agent_argument(agent),
		columns=[*columns, lead_field],
	)
	people = _people()
	users = set(source["users"])
	shown = rows[:MAX_RECORDS]
	return {
		"report": _describe(defn),
		"from_date": str(start),
		"to_date": str(end),
		"group": None if group is None else str(group),
		"columns": [{"field": f, "label": label} for f, label in source["columns"]],
		"records": [
			{
				"name": row.name,
				"lead": row.get(lead_field),
				"values": [
					people.get(row.get(f), row.get(f)) if f in users else _plain(row.get(f)) for f in columns
				],
			}
			for row in shown
		],
		"total": len(rows),
		"shown": len(shown),
		"truncated": len(rows) > len(shown),
		"sum": _total(defn, sum((_amount(defn, r) for r in rows), Decimal(0))),
	}


def _plain(value):
	return "" if value is None else value if isinstance(value, int | float | str) else str(value)


@sellos_api(COMPANY_ADMIN)
def refresh_report(report=None):
	"""Rebuild the summary table of one report, or of every enabled report, now instead of tonight."""
	names = (
		[_definition(report).name]
		if report
		else frappe.get_all(DEFINITION, filters={"enabled": 1}, pluck="name")
	)
	return {"refreshed": [refresh_summary(name) for name in names]}


@sellos_api(COMPANY_ADMIN)
def save_report_definition(values, report=None):
	"""Make a report (`values` holds its key) or change one (`report`). Only the fields in EDITABLE are read."""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if report:
		doc = _definition(report)
		doc.check_permission("write")
	else:
		doc = frappe.new_doc(DEFINITION)
		doc.check_permission("create")
		doc.report_key = values.get("report_key")
	for field in EDITABLE:
		if field in values:
			value = values[field]
			doc.set(field, json.dumps(value) if field == "filters" and isinstance(value, dict) else value)
	doc.save() if report else doc.insert()
	return _describe(doc)
