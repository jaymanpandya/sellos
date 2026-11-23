"""Saved views, export and scheduled email for the reports (SOS-P5-04).

* **Saved views.** A view is a report with its dates and agent filter kept under a name. It holds filters only,
  never figures, so a shared view shows each reader their own scope: opening it runs the report as that reader.
* **Export.** A Company Admin exports a report result as CSV or PDF: the same rows and totals the screen shows
  (both come from `engine.run_report_figures`), read as the signed in user. Nothing but a report result leaves:
  the raw `export` permission of the DocTypes stays with the Platform Admin (decided by Jayman, SOS-SETUP-34).
  A report holds no phone number by design (sources.py); a text cell that looks like one is masked anyway, a cell
  that a spreadsheet would read as a formula is made plain text, and every export is logged (Report Export Log).
* **Scheduled email.** A Report Schedule names a report, how often, the days covered and the people it goes to.
  An hourly job sends what is due. Each person is sent the report run as that person, so a Sales Manager or an
  Agent only gets the records they may see, and a person who may no longer read the report, or whose login is
  switched off, is skipped. Every delivery is logged too. Without an outgoing email account nothing is sent and
  the schedule says so.
"""

import base64
import csv
import io
import re
from datetime import datetime, time

import frappe
from frappe import _
from frappe.utils import add_days, cint, escape_html, getdate, now_datetime, today

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.crm.base import mask_phone
from sellos.reports import engine

VIEW = "Saved Report View"
SCHEDULE = "Report Schedule"
EXPORT_LOG = "Report Export Log"
FORMATS = {
	"csv": ("CSV", "text/csv", "csv"),
	"pdf": ("PDF", "application/pdf", "pdf"),
}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
FREQUENCIES = ("Daily", "Weekly", "Monthly")
MAX_DAYS = 3660
RECIPIENT_ROLES = (COMPANY_ADMIN, SALES_MANAGER, AGENT)
EDITABLE_VIEW = ("title", "report", "range_days", "from_date", "to_date", "agent", "shared")
EDITABLE_SCHEDULE = (
	"title",
	"report",
	"enabled",
	"frequency",
	"weekday",
	"day_of_month",
	"send_hour",
	"range_days",
	"agent",
	"file_format",
)
_PHONE_LIKE = re.compile(r"\+?\d[\d ()-]{7,}\d")
_DATE_LIKE = re.compile(r"\d{4}-\d\d-\d\d")


# ---- a report result as a table ---------------------------------------------------------------------


def mask_text(value) -> str:
	"""Text with anything that looks like a phone number (ten digits or more) masked. A date is left alone."""

	def hide(found):
		text = found.group(0)
		digits = sum(ch.isdigit() for ch in text)
		return mask_phone(text) if digits >= 10 and not _DATE_LIKE.fullmatch(text) else text

	return _PHONE_LIKE.sub(hide, "" if value is None else str(value))


def plain_cell(value) -> str:
	"""A text cell for a file: a phone number masked, and a cell a spreadsheet would run as a formula made text."""
	text = mask_text(value)
	return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def _figure(unit, value) -> str:
	if value is None:
		return ""
	if unit == "rupees":
		return f"{float(value):.2f}"
	return str(round(float(value)))


def build_table(defn, start, end, agent=None, user=None) -> dict:
	"""The report as the screen shows it, read as the signed in user (or as `user`, the person a scheduled email
	goes to): the columns, the rows (group label, number of records and, for a report that adds up a field, the
	total) and the totals row."""
	data = engine.run_report_figures(defn, start, end, agent, user)
	described = engine._describe(defn)
	adds = defn.measure == "Sum"
	measure = f"{described['measure_label']} ({described['unit']})" if described["unit"] != "number" else None
	columns = [described["group_label"], _("Records")]
	if adds:
		columns.append(measure or described["measure_label"])
	rows = [
		{"label": mask_text(row["label"]), "count": row["count"], "total": row["total"]}
		for row in data["rows"]
	]
	return {
		"report": described,
		"columns": [str(c) for c in columns],
		"rows": rows,
		"totals": {"label": str(_("Total")), **data["totals"]},
		"unit": described["unit"],
		"adds": adds,
		"from_date": str(start),
		"to_date": str(end),
	}


def _cells(table, row) -> list[str]:
	cells = [plain_cell(row["label"]), str(row["count"])]
	if table["adds"]:
		cells.append(_figure(table["unit"], row["total"]))
	return cells


def table_csv(table) -> str:
	out = io.StringIO()
	writer = csv.writer(out)
	writer.writerow(table["columns"])
	for row in [*table["rows"], table["totals"]]:
		writer.writerow(_cells(table, row))
	return out.getvalue()


def _title_lines(table) -> tuple[str, str]:
	described = table["report"]
	company = frappe.db.get_single_value("SellOS Settings", "company_name") or "SellOS"
	return (
		str(described["title"]),
		f"{company}. {described['date_label']} from {table['from_date']} to {table['to_date']}.",
	)


def table_html(table) -> str:
	title, subtitle = _title_lines(table)
	head = "".join(f"<th>{escape_html(c)}</th>" for c in table["columns"])
	body = "".join(
		"<tr>" + "".join(f"<td>{escape_html(c)}</td>" for c in _cells(table, row)) + "</tr>"
		for row in [*table["rows"], table["totals"]]
	)
	return (
		f"<h2>{escape_html(title)}</h2><p>{escape_html(subtitle)}</p>"
		f"<table border='1' cellspacing='0' cellpadding='6'><thead><tr>{head}</tr></thead>"
		f"<tbody>{body}</tbody></table>"
	)


def table_pdf(table) -> bytes:
	"""The table as a PDF written directly (no page layout program, which a server may lack or hang on), so the
	same rows come out on every machine."""
	from sellos.inventory.plain_pdf import build_table_pdf

	title, subtitle = _title_lines(table)
	return build_table_pdf(
		title, subtitle, table["columns"], [_cells(table, r) for r in [*table["rows"], table["totals"]]]
	)


def table_file(table, fmt) -> tuple[str, str, bytes]:
	"""(file name, mime type, bytes) of the table as CSV or PDF."""
	_label, mime, extension = FORMATS[fmt]
	content = table_csv(table).encode("utf-8") if fmt == "csv" else table_pdf(table)
	return f"{table['report']['key']}-{table['from_date']}-{table['to_date']}.{extension}", mime, content


def _log(defn, fmt, via, whose, start, end, rows, schedule=None) -> str:
	log = frappe.get_doc(
		{
			"doctype": EXPORT_LOG,
			"report": defn.name,
			"file_format": FORMATS[fmt][0],
			"via": via,
			"schedule": schedule,
			"exported_by": whose,
			"exported_on": now_datetime(),
			"from_date": start,
			"to_date": end,
			"row_count": rows,
		}
	)
	log.insert(ignore_permissions=True)  # the log is written by the export, so no role writes it by hand
	return log.name


# ---- saved views ------------------------------------------------------------------------------------


def validate_view(doc):
	if not doc.title or not doc.title.strip():
		frappe.throw(_("Give the view a name."))
	doc.title = doc.title.strip()[:140]
	doc.range_days = cint(doc.range_days)
	if doc.range_days < 0 or doc.range_days > MAX_DAYS:
		frappe.throw(_("The number of days must be between 1 and {0}.").format(MAX_DAYS))
	if doc.range_days:
		doc.from_date = doc.to_date = None
	elif doc.from_date and doc.to_date and getdate(doc.from_date) > getdate(doc.to_date):
		frappe.throw(_("The start date is after the end date."))
	if doc.agent and not frappe.db.exists("User", doc.agent):
		frappe.throw(_("That agent does not exist."))


def _view_dates(doc) -> tuple[str, str]:
	"""The dates a view opens on: the last N days ending today, or the dates it holds (empty is the default)."""
	if doc.range_days:
		end = getdate(today())
		return str(add_days(end, -(doc.range_days - 1))), str(end)
	return (str(doc.from_date) if doc.from_date else ""), (str(doc.to_date) if doc.to_date else "")


def _describe_view(doc, defn) -> dict:
	start, end = _view_dates(doc)
	return {
		"name": doc.name,
		"title": doc.title,
		"report": doc.report,
		"report_title": defn.title,
		"range_days": cint(doc.range_days),
		"from_date": start,
		"to_date": end,
		"agent": doc.agent or "",
		"shared": bool(doc.shared),
		"mine": doc.owner == frappe.session.user,
		"owner_name": frappe.db.get_value("User", doc.owner, "full_name") or doc.owner,
	}


@sellos_api(COMPANY_ADMIN, SALES_MANAGER, AGENT)
def list_report_views():
	"""The views the reader made and the views others shared, for the reports the reader may read."""
	roles = frappe.get_roles()
	user = frappe.session.user
	found = []
	for name in frappe.get_all(VIEW, pluck="name", order_by="title asc"):
		doc = frappe.get_doc(VIEW, name)
		if doc.owner != user and not doc.shared:
			continue
		if not frappe.db.exists(engine.DEFINITION, doc.report):
			continue
		defn = frappe.get_doc(engine.DEFINITION, doc.report)
		if engine._reads(defn, roles):
			found.append(_describe_view(doc, defn))
	return {"views": found}


@sellos_api(COMPANY_ADMIN, SALES_MANAGER, AGENT)
def save_report_view(values, view=None):
	"""Save a view (`values` holds its title, report, dates or days, agent and whether it is shared), or change
	one the reader made (`view`). The reader must be able to read the report."""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if view:
		doc = frappe.get_doc(VIEW, view)
		if doc.owner != frappe.session.user:
			frappe.throw(_("Only the person who made a view may change it."), frappe.PermissionError)
	else:
		doc = frappe.new_doc(VIEW)
	for field in EDITABLE_VIEW:
		if field in values:
			doc.set(
				field, values[field] or None if field in ("agent", "from_date", "to_date") else values[field]
			)
	defn = engine._readable(doc.report)
	doc.save(ignore_permissions=True) if view else doc.insert(ignore_permissions=True)
	return _describe_view(doc, defn)


@sellos_api(COMPANY_ADMIN, SALES_MANAGER, AGENT)
def delete_report_view(view):
	"""Delete a saved view: the one who made it, or a Company Admin. A view holds filters, not records."""
	if not frappe.db.exists(VIEW, view):
		frappe.throw(_("This view does not exist."), frappe.DoesNotExistError)
	if (
		frappe.db.get_value(VIEW, view, "owner") != frappe.session.user
		and COMPANY_ADMIN not in frappe.get_roles()
	):
		frappe.throw(_("Only the person who made a view may delete it."), frappe.PermissionError)
	frappe.delete_doc(VIEW, view, ignore_permissions=True)
	return {"deleted": view}


# ---- export -----------------------------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def export_report(report, from_date=None, to_date=None, agent=None, format="csv"):
	"""A report result as a CSV or PDF file for a range of dates: the rows and totals the screen shows for the
	same dates, as the file (`content`, base64) and as data. The export is logged."""
	if format not in FORMATS:
		frappe.throw(_("Export a report as CSV or PDF."))
	defn = engine._readable(report)
	start, end = engine._range(from_date, to_date)
	table = build_table(defn, start, end, engine._agent_argument(agent))
	filename, mime, content = table_file(table, format)
	log = _log(defn, format, "Screen", frappe.session.user, start, end, len(table["rows"]))
	return {
		"report": defn.name,
		"title": defn.title,
		"format": FORMATS[format][0],
		"filename": filename,
		"mime": mime,
		"content": base64.b64encode(content).decode("ascii"),
		"columns": table["columns"],
		"rows": table["rows"],
		"totals": table["totals"],
		"from_date": str(start),
		"to_date": str(end),
		"export_log": log,
	}


# ---- schedules --------------------------------------------------------------------------------------


def next_run(doc, after) -> datetime:
	"""The first moment after `after` that the schedule falls due."""
	hour = min(max(cint(doc.send_hour), 0), 23)
	for offset in range(0, 40):
		day = add_days(getdate(after), offset)
		if doc.frequency == "Daily":
			due = True
		elif doc.frequency == "Weekly":
			due = WEEKDAYS[day.weekday()] == doc.weekday
		else:
			due = day.day == cint(doc.day_of_month)
		if due and datetime.combine(day, time(hour)) > after:
			return datetime.combine(day, time(hour))
	frappe.throw(_("This schedule never falls due."))


def _may_read(user, defn) -> bool:
	return engine._reads(defn, frappe.get_roles(user))


def validate_schedule(doc):
	if not doc.title or not doc.title.strip():
		frappe.throw(_("Give the schedule a name."))
	if doc.frequency not in FREQUENCIES:
		frappe.throw(_("Choose daily, weekly or monthly."))
	doc.send_hour = cint(doc.send_hour)
	if not 0 <= doc.send_hour <= 23:
		frappe.throw(_("The hour must be between 0 and 23."))
	if doc.frequency == "Weekly" and doc.weekday not in WEEKDAYS:
		frappe.throw(_("Choose a day of the week."))
	doc.day_of_month = cint(doc.day_of_month) or 1
	if doc.frequency == "Monthly" and not 1 <= doc.day_of_month <= 28:
		frappe.throw(_("The day of the month must be between 1 and 28."))
	doc.range_days = cint(doc.range_days)
	if not 1 <= doc.range_days <= 366:
		frappe.throw(_("The days covered must be between 1 and 366."))
	if doc.agent and not frappe.db.exists("User", doc.agent):
		frappe.throw(_("That agent does not exist."))
	if not doc.recipients:
		frappe.throw(_("Choose at least one person to send the report to."))
	defn = engine._definition(doc.report)
	seen = set()
	for row in doc.recipients:
		if row.user in seen:
			frappe.throw(_("{0} is listed twice.").format(row.user))
		seen.add(row.user)
		if not frappe.db.get_value("User", row.user, "enabled"):
			frappe.throw(_("{0} has no active login.").format(row.user))
		if not _may_read(row.user, defn):
			frappe.throw(_("{0} may not read this report, so it cannot be sent to them.").format(row.user))
	timing = ("frequency", "weekday", "day_of_month", "send_hour", "enabled")
	if not doc.enabled:
		doc.next_run = None
	elif doc.is_new() or not doc.next_run or any(doc.has_value_changed(f) for f in timing):
		doc.next_run = next_run(doc, now_datetime())


def _covered(doc) -> tuple:
	end = add_days(getdate(today()), -1)
	return add_days(end, -(cint(doc.range_days) - 1)), end


def _email_body(table, who) -> str:
	return (
		f"<p>{_('Hello {0},').format(escape_html(who))}</p>"
		f"<p>{_('Here is the report you asked to be sent. It holds only the records you may see.')}</p>"
		f"{table_html(table)}"
	)


def _deliver(doc, recipient, start, end) -> str:
	"""Send the report to one person, run as that person. Returns what happened, in a few words."""
	user = frappe.db.get_value("User", recipient, ["enabled", "email", "full_name"], as_dict=True)
	if not user or not user.enabled or not user.email:
		return "Skipped: no active login"
	fmt = doc.file_format.lower()
	defn = engine._definition(doc.report)
	if not engine._reads(defn, frappe.get_roles(recipient)):
		return "Skipped: may not read this report"
	# The report is read as the recipient (their roles, their team's and their own records), not as the job.
	table = build_table(defn, start, end, doc.agent or None, user=recipient)
	filename, _mime, content = table_file(table, fmt)
	try:
		frappe.sendmail(
			recipients=[user.email],
			subject=_("{0}: {1}").format(doc.title, defn.title),
			message=_email_body(table, user.full_name or user.email),
			attachments=[{"fname": filename, "fcontent": content}],
			now=True,
		)
	except Exception:
		frappe.log_error(title="SOS-P5-04 scheduled report email failed")
		return "Failed: the email could not be sent"
	_log(defn, fmt, "Email", recipient, start, end, len(table["rows"]), schedule=doc.name)
	return "Sent"


def send_schedule(name) -> dict:
	"""Send one schedule now, to every person on it, and record what happened to each. The schedule's next
	delivery is not changed."""
	from sellos.access.users import mail_ready

	doc = frappe.get_doc(SCHEDULE, name)
	start, end = _covered(doc)
	ready = mail_ready()
	results = {}
	for row in doc.recipients:
		status = _deliver(doc, row.user, start, end) if ready else "Not sent: no outgoing email account"
		frappe.db.set_value(
			"Report Schedule Recipient", row.name, "last_status", status, update_modified=False
		)
		results[row.user] = status
	sent = sum(1 for s in results.values() if s == "Sent")
	frappe.db.set_value(
		SCHEDULE,
		name,
		{
			"last_sent_on": now_datetime() if sent else doc.last_sent_on,
			"last_result": f"{sent} of {len(results)} sent",
		},
		update_modified=False,
	)
	return {"schedule": name, "from_date": str(start), "to_date": str(end), "results": results}


def send_due_schedules() -> list[dict]:
	"""The hourly job: send every enabled schedule that is due. The next delivery is set before the send, so a
	failure never sends a schedule twice. One schedule that fails is logged and the others go on."""
	now = now_datetime()
	done = []
	for name in frappe.get_all(SCHEDULE, filters={"enabled": 1, "next_run": ["<=", now]}, pluck="name"):
		try:
			doc = frappe.get_doc(SCHEDULE, name)
			frappe.db.set_value(SCHEDULE, name, "next_run", next_run(doc, now), update_modified=False)
			done.append(send_schedule(name))
		except Exception:
			frappe.log_error(title=f"SOS-P5-04 scheduled report failed for {name}")
	return done


def _describe_schedule(doc) -> dict:
	return {
		"name": doc.name,
		"title": doc.title,
		"report": doc.report,
		"report_title": frappe.db.get_value(engine.DEFINITION, doc.report, "title"),
		"enabled": bool(doc.enabled),
		"frequency": doc.frequency,
		"weekday": doc.weekday,
		"day_of_month": cint(doc.day_of_month),
		"send_hour": cint(doc.send_hour),
		"range_days": cint(doc.range_days),
		"agent": doc.agent or "",
		"file_format": doc.file_format,
		"recipients": [{"user": r.user, "last_status": r.last_status or ""} for r in doc.recipients],
		"next_run": str(doc.next_run) if doc.next_run else None,
		"last_sent_on": str(doc.last_sent_on) if doc.last_sent_on else None,
		"last_result": doc.last_result or "",
	}


def _people() -> list[dict]:
	"""The people a report may be sent to: active Company Admins, Sales Managers and Agents."""
	roles = {}
	for row in frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "role": ["in", list(RECIPIENT_ROLES)]},
		fields=["parent", "role"],
	):
		roles.setdefault(row.parent, set()).add(row.role)
	users = frappe.get_all(
		"User",
		filters={"name": ["in", list(roles)], "enabled": 1},
		fields=["name", "full_name"],
		order_by="full_name",
	)
	return [{"email": u.name, "name": u.full_name or u.name, "roles": sorted(roles[u.name])} for u in users]


@sellos_api(COMPANY_ADMIN)
def list_report_schedules():
	"""Every schedule, the people a report may be sent to, and whether this site can send email."""
	from sellos.access.users import mail_ready

	return {
		"schedules": [
			_describe_schedule(frappe.get_doc(SCHEDULE, n))
			for n in frappe.get_all(SCHEDULE, pluck="name", order_by="title asc")
		],
		"people": _people(),
		"mail_ready": mail_ready(),
	}


@sellos_api(COMPANY_ADMIN)
def save_report_schedule(values, schedule=None):
	"""Make a schedule (`values` holds its fields and `recipients`, a list of emails) or change one."""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	doc = frappe.get_doc(SCHEDULE, schedule) if schedule else frappe.new_doc(SCHEDULE)
	for field in EDITABLE_SCHEDULE:
		if field in values:
			doc.set(field, (values[field] or None) if field == "agent" else values[field])
	if "recipients" in values:
		kept = {r.user: r.last_status for r in doc.recipients}
		doc.set("recipients", [])
		for email in values["recipients"] or []:
			doc.append("recipients", {"user": email, "last_status": kept.get(email)})
	doc.save() if schedule else doc.insert()
	return _describe_schedule(doc)


@sellos_api(COMPANY_ADMIN)
def delete_report_schedule(schedule):
	if not frappe.db.exists(SCHEDULE, schedule):
		frappe.throw(_("This schedule does not exist."), frappe.DoesNotExistError)
	frappe.delete_doc(SCHEDULE, schedule)
	return {"deleted": schedule}


@sellos_api(COMPANY_ADMIN)
def send_report_schedule_now(schedule):
	"""Send a schedule's report now, for the days it covers, without changing its next delivery."""
	if not frappe.db.exists(SCHEDULE, schedule):
		frappe.throw(_("This schedule does not exist."), frappe.DoesNotExistError)
	return send_schedule(schedule)
