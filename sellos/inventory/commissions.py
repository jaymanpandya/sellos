"""Commission rates and payouts (SOS-P7-04), on top of SOS-P4-06's deals.

* **Rates.** A Company Admin sets a rate per project: a percent of the agreement value (the deal's price) or a fixed
  amount, from a start date. A rate for one partner firm overrides the project's own rate for that firm. A rate is
  never changed: a new one with a later start date replaces it and the earlier ones are kept.
* **Calculation.** When a deal with a channel partner share is approved, the rate in force on the booking date (the
  deal date) gives the commission at the rate, and the partner's due is its share of that: the share percent of the
  split. A firm's own rate in force beats the project's. A rate added or changed after the booking date never
  applies to it. The sums are made in whole paise, half up. A deal for a property has no project, so it has no rate.
* **Payouts.** One Commission Payout per deal and firm is made in status Due. A Company Admin moves it to
  Approved and Paid (with the payment reference and date), or puts it On hold with a reason. A deal whose split was
  approved before a rate existed is listed as waiting, and the payout is made when the rate is added.
* **Who sees what.** A partner reads their own firm's payouts and a statement for a date range, and nobody else's. A
  Company Admin exports one firm's statement as a report result: only the rows they may read, every export logged.
  No role has the raw export permission of the DocTypes.
"""

import csv
import io
from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today

from sellos.access.partner_firms import FIRM, firm_of, is_pure_partner
from sellos.access.registry import sellos_api
from sellos.access.roles import CHANNEL_PARTNER, COMPANY_ADMIN
from sellos.crm.base import mask_phone
from sellos.sellos.doctype.commission_payout.commission_payout import (
	APPROVED,
	DUE,
	HOLD,
	PAID,
	STATUSES,
)
from sellos.sellos.doctype.commission_rate.commission_rate import FIXED, PERCENTAGE, RATE_TYPES

CENT = Decimal("0.01")
HUNDRED = Decimal("100")
RATE_FIELDS = ("project", "partner_firm", "rate_type", "value", "start_date")
PARTNER_PARTY = "Channel Partner"
CSV_COLUMNS = (
	("payout", "Payout"),
	("deal", "Deal"),
	("target", "Project and unit"),
	("booking_date", "Booking date"),
	("agreement_value", "Agreement value (Rs)"),
	("rate_basis", "Rate"),
	("partner_percent", "Share (%)"),
	("commission_due", "Commission due (Rs)"),
	("status", "Status"),
	("payment_reference", "Payment reference"),
	("paid_on", "Paid on"),
)


def _dec(value) -> Decimal:
	return Decimal(str(flt(value))).quantize(CENT, rounding=ROUND_HALF_UP)


def _statement_range(from_date, to_date):
	"""The two end days of a statement. The default is the last 12 months, ending today, because a payout is
	often paid months after the booking."""
	end = getdate(to_date) if to_date else getdate(today())
	start = getdate(from_date) if from_date else add_days(end, -364)
	if start > end:
		frappe.throw(_("The start date is after the end date."))
	return start, end


def _flag(value) -> bool:
	return str(value).lower() in ("1", "true", "yes")


def _values(values) -> dict:
	return frappe.parse_json(values) if isinstance(values, str) else (values or {})


# --- The calculation ------------------------------------------------------------------------------


def rate_in_force(project, firm, on_date):
	"""The rate that applies to a deal of this project and firm on this date, or None. The firm's own rate in
	force beats the project's. Of the rates in force the one with the latest start date wins. Archived rates
	(entered by mistake) are not used."""
	for owner in (firm, ""):
		if owner == "" and not project:
			break
		rows = frappe.get_all(
			"Commission Rate",
			filters={
				"project": project,
				"archived": 0,
				"start_date": ("<=", getdate(on_date)),
				"partner_firm": owner if owner else ("is", "not set"),
			},
			fields=["name", "rate_type", "value", "start_date"],
			order_by="start_date desc, creation desc",
			limit=1,
		)
		if rows:
			return rows[0]
	return None


def commission_at_rate(price, rate) -> Decimal:
	"""The commission a rate gives on a price, to the paisa."""
	if rate["rate_type"] == PERCENTAGE:
		return (_dec(price) * _dec(rate["value"]) / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)
	return _dec(rate["value"])


def partner_due(price, rate, percent) -> tuple[Decimal, Decimal]:
	"""(the commission at the rate, the partner's due): the due is the partner's share of the commission."""
	total = commission_at_rate(price, rate)
	return total, (total * _dec(percent) / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)


def describe_rate(rate) -> str:
	if rate["rate_type"] == PERCENTAGE:
		return _("{0}% of the agreement value").format(f"{flt(rate['value']):g}")
	return _("A fixed Rs {0}").format(f"{flt(rate['value']):,.2f}")


def _project_of(deal):
	return frappe.db.get_value("Unit", deal.unit, "project") if deal.unit else None


def _worked_out(deal, row, project) -> dict | None:
	rate = rate_in_force(project, row.partner_firm, deal.deal_date)
	if not rate:
		return None
	total, due = partner_due(deal.price, rate, row.percent)
	return {
		"project": project,
		"booking_date": getdate(deal.deal_date),
		"agreement_value": float(_dec(deal.price)),
		"rate": rate["name"],
		"rate_basis": describe_rate(rate),
		"commission_total": float(total),
		"partner_percent": float(_dec(row.percent)),
		"commission_due": float(due),
	}


def make_payouts(deal) -> list[str]:
	"""Make the Due payout of every channel partner share of an approved deal, and return the names made. A payout
	that is still Due is worked out again (the split may have been reopened and corrected); one that has moved on
	is left as it is. A share with no rate in force gets no payout yet (see `waiting_deals`). Run again, it makes
	nothing twice."""
	made = []
	project = _project_of(deal)
	for row in deal.splits:
		if row.party_type != PARTNER_PARTY or not row.partner_firm:
			continue
		figures = _worked_out(deal, row, project)
		if not figures:
			continue
		name = frappe.db.get_value("Commission Payout", {"deal": deal.name, "partner_firm": row.partner_firm})
		if name:
			payout = frappe.get_doc("Commission Payout", name)
			if payout.status != DUE:
				continue
			payout.flags.recalculating = True
			payout.update(figures)
			payout.save(ignore_permissions=True)
			continue
		payout = frappe.get_doc(
			{
				"doctype": "Commission Payout",
				"deal": deal.name,
				"partner_firm": row.partner_firm,
				"status": DUE,
				**figures,
			}
		)
		payout.insert(ignore_permissions=True)
		made.append(payout.name)
	return made


def waiting_deals() -> list[dict]:
	"""Approved deals with a channel partner share that has no payout, and why."""
	waiting = []
	for name in frappe.get_all("Deal", filters={"approval_status": "Approved", "archived": 0}, pluck="name"):
		deal = frappe.get_doc("Deal", name)
		project = _project_of(deal)
		for row in deal.splits:
			if row.party_type != PARTNER_PARTY or frappe.db.exists(
				"Commission Payout", {"deal": name, "partner_firm": row.partner_firm}
			):
				continue
			waiting.append(
				{
					"deal": name,
					"partner_firm": row.partner_firm,
					"firm_name": frappe.db.get_value(FIRM, row.partner_firm, "firm_name") or row.partner_firm,
					"reason": _("Add a commission rate for the project that starts on or before {0}.").format(
						deal.deal_date
					)
					if project
					else _("A deal for a property has no project, so no rate applies."),
				}
			)
	return waiting


# --- What is shown --------------------------------------------------------------------------------


def _target(deal) -> str:
	if deal.unit:
		project, number = frappe.db.get_value("Unit", deal.unit, ["project", "unit_number"])
		return f"{frappe.db.get_value('Project', project, 'project_name') or project} {number}"
	return frappe.db.get_value("Property", deal.property, "title") or deal.property or ""


def _payout_row(doc) -> dict:
	deal = frappe.get_doc("Deal", doc.deal)
	return {
		"name": doc.name,
		"deal": doc.deal,
		"target": _target(deal),
		"partner_firm": doc.partner_firm,
		"firm_name": frappe.db.get_value(FIRM, doc.partner_firm, "firm_name") or doc.partner_firm,
		"status": doc.status,
		"booking_date": str(doc.booking_date or ""),
		"agreement_value": doc.agreement_value,
		"rate_basis": doc.rate_basis or "",
		"commission_total": doc.commission_total,
		"partner_percent": doc.partner_percent,
		"commission_due": doc.commission_due,
		"hold_reason": doc.hold_reason or "",
		"held_from": doc.held_from or "",
		"payment_reference": doc.payment_reference or "",
		"paid_on": str(doc.paid_on or ""),
	}


def _rate_row(doc) -> dict:
	return {
		"name": doc.name,
		"project": doc.project,
		"project_name": frappe.db.get_value("Project", doc.project, "project_name") or doc.project,
		"partner_firm": doc.partner_firm or "",
		"firm_name": (frappe.db.get_value(FIRM, doc.partner_firm, "firm_name") if doc.partner_firm else "")
		or "",
		"rate_type": doc.rate_type,
		"value": doc.value,
		"start_date": str(doc.start_date),
		"archived": int(doc.archived or 0),
	}


def _totals(rows) -> dict:
	totals = {s: Decimal(0) for s in STATUSES}
	for row in rows:
		totals[row["status"]] += _dec(row["commission_due"])
	return {
		"by_status": {s: float(v) for s, v in totals.items()},
		"total": float(sum(totals.values(), Decimal(0))),
		"count": len(rows),
	}


def _statement(firm, start, end) -> dict:
	"""One firm's payouts booked from start to end, read through the permission rules of the signed in user."""
	names = frappe.get_list(
		"Commission Payout",
		filters=[
			["partner_firm", "=", firm],
			["booking_date", ">=", start],
			["booking_date", "<=", end],
		],
		pluck="name",
		order_by="booking_date asc, name asc",
		limit_page_length=0,
	)
	rows = [_payout_row(frappe.get_doc("Commission Payout", n)) for n in names]
	return {"rows": rows, "totals": _totals(rows)}


def _overview(include_archived=False) -> dict:
	filters = {} if include_archived else {"archived": 0}
	rates = [
		_rate_row(frappe.get_doc("Commission Rate", n))
		for n in frappe.get_all(
			"Commission Rate", filters=filters, pluck="name", order_by="project asc, start_date desc"
		)
	]
	payouts = [
		_payout_row(frappe.get_doc("Commission Payout", n))
		for n in frappe.get_all("Commission Payout", pluck="name", order_by="creation desc")
	]
	return {
		"rates": rates,
		"payouts": payouts,
		"waiting": waiting_deals(),
		"totals": _totals(payouts),
		"projects": [
			{"value": p.name, "label": p.project_name or p.name}
			for p in frappe.get_all("Project", filters={"archived": 0}, fields=["name", "project_name"])
		],
		"firms": [
			{"value": f.name, "label": f.firm_name}
			for f in frappe.get_all(FIRM, fields=["name", "firm_name"], order_by="firm_name asc")
		],
		"rate_types": list(RATE_TYPES),
	}


# --- The Company Admin ----------------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def commission_overview(include_archived=0):
	"""The commission rates, every payout with its totals by status, the approved deals still waiting for a rate,
	and what a rate can be made from."""
	return _overview(_flag(include_archived))


@sellos_api(COMPANY_ADMIN)
def save_commission_rate(values):
	"""Add a commission rate for a project (and optionally one partner firm), as a percentage or a fixed amount,
	from a start date. Earlier rates are kept. Approved deals that were waiting for a rate get their payouts."""
	values = _values(values)
	doc = frappe.get_doc(
		{
			"doctype": "Commission Rate",
			**{k: (values.get(k) or None) if k == "partner_firm" else values.get(k) for k in RATE_FIELDS},
		}
	)
	doc.insert()
	made = make_missing_payouts()
	return {"name": doc.name, "payouts_made": made, **_overview()}


@sellos_api(COMPANY_ADMIN)
def set_commission_rate_archived(name, archived=1):
	"""Archive a rate that was entered by mistake, or restore it. It is kept, and an archived rate is not used."""
	if not frappe.db.exists("Commission Rate", name):
		frappe.throw(_("There is no commission rate {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Commission Rate", name)
	doc.check_permission("write")
	doc.archived = 1 if _flag(archived) else 0
	doc.save()
	return {"name": doc.name, **_overview()}


def make_missing_payouts() -> list[str]:
	made = []
	for name in {w["deal"] for w in waiting_deals()}:
		made += make_payouts(frappe.get_doc("Deal", name))
	return made


@sellos_api(COMPANY_ADMIN)
def create_missing_payouts():
	"""Make the payouts of approved deals that were waiting for a rate, now that one is in force."""
	return {"payouts_made": make_missing_payouts(), **_overview()}


@sellos_api(COMPANY_ADMIN)
def move_payout(name, to, payment_reference=None, paid_on=None, reason=None):
	"""Move a payout: Due to Approved, Approved to Paid (with the payment reference and date), either to On hold
	with a reason, and a held payout back to where it was held from. Every change is logged."""
	if not frappe.db.exists("Commission Payout", name):
		frappe.throw(_("There is no payout {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Commission Payout", name)
	doc.check_permission("write")
	if to not in STATUSES:
		frappe.throw(_("A payout is Due, Approved, Paid or On hold."))
	doc.status = to
	if to == PAID:
		doc.payment_reference, doc.paid_on = payment_reference, paid_on
	if to == HOLD:
		doc.hold_reason = reason
	doc.save()
	return {"name": doc.name, **_overview()}


@sellos_api(COMPANY_ADMIN)
def export_partner_statement(firm, from_date=None, to_date=None):
	"""A firm's statement for the dates as a report result: the columns, the rows, the totals and the same rows
	as CSV text. It holds only what the signed in Company Admin may read, the contact phone masked, and the
	export is logged."""
	if not frappe.db.exists(FIRM, firm):
		frappe.throw(_("There is no partner firm {0}.").format(firm), frappe.DoesNotExistError)
	start, end = _statement_range(from_date, to_date)
	statement = _statement(firm, start, end)
	table = io.StringIO()
	writer = csv.writer(table)
	writer.writerow([label for _key, label in CSV_COLUMNS])
	for row in statement["rows"]:
		writer.writerow([_safe(row.get(key, "")) for key, _label in CSV_COLUMNS])
	log = frappe.get_doc(
		{
			"doctype": "Commission Statement Export",
			"partner_firm": firm,
			"from_date": start,
			"to_date": end,
			"row_count": len(statement["rows"]),
			"total_due": statement["totals"]["total"],
			"exported_by": frappe.session.user,
			"exported_on": frappe.utils.now_datetime(),
		}
	)
	log.insert(ignore_permissions=True)  # the log is written by the export, so no role writes it by hand
	doc = frappe.get_doc(FIRM, firm)
	return {
		"firm": firm,
		"firm_name": doc.firm_name,
		"firm_phone_masked": mask_phone(doc.phone),
		"from_date": str(start),
		"to_date": str(end),
		"columns": [{"field": k, "label": label} for k, label in CSV_COLUMNS],
		"rows": statement["rows"],
		"totals": statement["totals"],
		"csv": table.getvalue(),
		"filename": f"commission-statement-{firm}-{start}-{end}.csv",
		"export_log": log.name,
	}


def _safe(value):
	"""A CSV cell that a spreadsheet would read as a formula is made plain text."""
	text = "" if value is None else str(value)
	return "'" + text if text[:1] in ("=", "+", "-", "@") else text


# --- The partner ----------------------------------------------------------------------------------


@sellos_api(CHANNEL_PARTNER)
def partner_commission(from_date=None, to_date=None):
	"""The signed in partner's own payouts booked in the dates, with the totals by status: their statement. A login
	with no firm has none."""
	user = frappe.session.user
	if not is_pure_partner(frappe.get_roles(user)):
		frappe.throw(_("This statement is for a channel partner login."), frappe.PermissionError)
	start, end = _statement_range(from_date, to_date)
	firm = firm_of(user)
	empty = {"rows": [], "totals": _totals([])}
	return {
		"firm": firm,
		"from_date": str(start),
		"to_date": str(end),
		**(_statement(firm, start, end) if firm else empty),
	}


# --- Who may read a payout ------------------------------------------------------------------------


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	roles = frappe.get_roles(user)
	if COMPANY_ADMIN in roles or "System Manager" in roles:
		return ""
	firm = firm_of(user) if CHANNEL_PARTNER in roles else None
	if firm:
		return f"`tabCommission Payout`.`partner_firm` = {frappe.db.escape(firm)}"
	return "1=0"


def has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	if COMPANY_ADMIN in roles or "System Manager" in roles:
		return True
	if CHANNEL_PARTNER in roles:
		firm = firm_of(user)
		return bool(firm) and (ptype or "read") in ("read", "select") and doc.get("partner_firm") == firm
	return False
