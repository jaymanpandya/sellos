"""Book a unit from a lead, and cancel the booking (SOS-P7-10).

* An Agent (or a Company Admin) books an Available unit, or one held for this lead, for a lead they may
  write, with the agreed price, the booking amount and, when there is one, the cost sheet of that unit.
* Confirming does three things in one transaction: it makes the Deal (SOS-P4-06) for the lead's client,
  marks the unit Booked (SOS-P7-06) and moves the lead to the Booking stage (SOS-P1-07). The unit's row is
  locked first, so of two bookings of one unit exactly one succeeds. A failure at any step rolls all of it
  back to a savepoint, so nothing is left half done.
* A Booked, Sold, Blocked or archived unit, and a unit held for another lead, is refused.
* When the lead has a protected channel partner registration (SOS-P7-02) the booking moves it to Booked
  and the Deal's commission split includes the partner's firm.
* Cancelling needs a reason. The unit goes back to Available, the Deal is marked Cancelled (never deleted)
  with who, when and why, and the lead's stage is left for the agent to choose.
* Consent never blocks a booking. The lead's consent warning is returned for the screen, as everywhere else.

The deal's commission split is a starting split that a Company Admin corrects before approving it
(SOS-P4-06): with a partner 40% partner, 20% agent, 40% company; without one 50% agent, 50% company; a
share with nobody to earn it goes to the company.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

from sellos.access import partner_registrations
from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.crm import consent, pipeline
from sellos.inventory import holds
from sellos.inventory.base import AVAILABLE, BOOKED, HELD, squash
from sellos.sellos.doctype.channel_partner_firm.channel_partner_firm import APPROVED as FIRM_APPROVED
from sellos.sellos.doctype.deal.deal import (
	ACTIVE,
	AGENT_PARTY,
	CANCELLED,
	COMPANY_PARTY,
	PARTNER_PARTY,
	PENDING,
)

BOOKERS = (COMPANY_ADMIN, AGENT)
SAVEPOINT = "sellos_booking"
SHARES_WITH_PARTNER = {PARTNER_PARTY: 40, AGENT_PARTY: 20, COMPANY_PARTY: 40}
SHARES_WITHOUT_PARTNER = {AGENT_PARTY: 50, COMPANY_PARTY: 50}


def _lead(name, write=True):
	if not name or not frappe.db.exists("Lead", name):
		frappe.throw(_("There is no lead {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Lead", name)
	doc.check_permission("write" if write else "read")
	return doc


def _unit_label(unit) -> str:
	row = frappe.db.get_value("Unit", unit, ["project", "unit_number", "tower"], as_dict=True)
	if not row:
		return unit
	project = frappe.db.get_value("Project", row.project, "project_name") or row.project
	return f"{project} {row.unit_number}"


def _earning_agent(lead) -> str | None:
	"""The agent who earns the agent share: the lead's owner, else the one booking; None when neither is one."""
	for user in (lead.assigned_to, frappe.session.user):
		if user and frappe.db.exists("User", user):
			roles = frappe.get_roles(user)
			if AGENT in roles or SALES_MANAGER in roles:
				return user
	return None


def _protected_partner(lead) -> str | None:
	"""The Approved firm whose registration protects the lead, or None."""
	if not partner_registrations.is_protected(lead):
		return None
	firm = frappe.db.get_value(
		partner_registrations.REG, {"lead": lead}, "partner_firm", order_by="creation desc"
	)
	if firm and frappe.db.get_value("Channel Partner Firm", firm, "status") == FIRM_APPROVED:
		return firm
	return None


def _splits(lead, firm) -> list[dict]:
	agent = _earning_agent(lead)
	shares = dict(SHARES_WITH_PARTNER if firm else SHARES_WITHOUT_PARTNER)
	if not agent:
		shares[COMPANY_PARTY] += shares.pop(AGENT_PARTY, 0)
	rows = []
	for party, percent in shares.items():
		row = {"party_type": party, "percent": percent}
		if party == AGENT_PARTY:
			row["agent"] = agent
		elif party == PARTNER_PARTY:
			row["partner_firm"] = firm
		rows.append(row)
	return rows


def _commission(price, project, firm) -> float:
	"""The commission at the rate in force today (the firm's own rate beats the project's), or 0 when none."""
	from sellos.inventory.commissions import commission_at_rate, rate_in_force

	rate = rate_in_force(project, firm, today())
	return float(commission_at_rate(price, rate)) if rate else 0.0


def _check_unit_bookable(unit, row, lead, at):
	number = frappe.db.get_value("Unit", unit, "unit_number")
	if row.archived:
		frappe.throw(_("Unit {0} is archived and can not be booked.").format(number))
	if holds._lapsed(row, at):
		holds._change(unit, AVAILABLE, _("The hold expired."))
		return
	if row.status == HELD:
		if row.held_for_lead == lead:
			return
		holds._refuse_held(unit, row)
	if row.status != AVAILABLE:
		frappe.throw(_("Unit {0} is {1}, so it can not be booked.").format(number, row.status))


def _check_cost_sheet(cost_sheet, unit):
	if not cost_sheet:
		return
	if (
		not frappe.db.exists("Cost Sheet", cost_sheet)
		or frappe.db.get_value("Cost Sheet", cost_sheet, "unit") != unit
	):
		frappe.throw(_("Choose a cost sheet of this unit."))
	if not frappe.has_permission("Cost Sheet", "read", doc=cost_sheet):
		frappe.throw(_("You may not use that cost sheet."), frappe.PermissionError)


def _amount(value, label) -> float:
	try:
		amount = flt(value)
	except Exception:
		amount = 0
	if amount <= 0:
		frappe.throw(_("Enter the {0}, more than zero.").format(label))
	return amount


def book(lead, unit, price, booking_amount, cost_sheet=None) -> dict:
	"""Book a unit for a lead in one transaction. The caller has checked the role."""
	frappe.db.savepoint(SAVEPOINT)
	try:
		# The unit's row is locked before anything else is read, so the second of two bookings waits for the
		# first, then sees Booked. It stays locked to the end of the transaction.
		row = holds._lock(unit)
		doc = _lead(lead)
		if doc.archived:
			frappe.throw(_("An archived lead can not book a unit."))
		if (doc.get("pipeline") or pipeline.BUYER) != pipeline.BUYER:
			frappe.throw(_("Only a buyer lead books a unit."))
		if not doc.client:
			frappe.throw(_("The lead has no client. Add the buyer first."))
		price = _amount(price, _("agreed price"))
		booking_amount = _amount(booking_amount, _("booking amount"))
		if booking_amount > price:
			frappe.throw(_("The booking amount can not be more than the agreed price."))
		stage = pipeline.stage_doc_name(pipeline.BUYER, pipeline.BOOKING)
		if not frappe.db.exists(pipeline.STAGE, stage):
			frappe.throw(_("The pipeline has no Booking stage."))
		cost_sheet = squash(cost_sheet) or None
		_check_unit_bookable(unit, row, lead, holds.now())
		_check_cost_sheet(cost_sheet, unit)
		firm = _protected_partner(lead)
		project = frappe.db.get_value("Unit", unit, "project")
		deal = frappe.get_doc(
			{
				"doctype": "Deal",
				"client": doc.client,
				"lead": lead,
				"unit": unit,
				"price": price,
				"booking_amount": booking_amount,
				"cost_sheet": cost_sheet,
				"booked_by": frappe.session.user,
				"deal_date": getdate(today()),
				"commission_amount": _commission(price, project, firm),
				"approval_status": PENDING,
				"deal_status": ACTIVE,
				"splits": _splits(doc, firm),
			}
		)
		deal.insert(ignore_permissions=True)
		holds._change(unit, BOOKED, _("Booked for deal {0}.").format(deal.name))
		moved = pipeline.move_lead(lead, stage)
		partner_registrations.mark_booked(lead)
	except Exception:
		frappe.db.rollback(save_point=SAVEPOINT)
		raise
	return {"deal": deal.name, "stage": moved["stage"], "warning": moved["warning"]}


def cancel(deal, reason) -> dict:
	"""Cancel a booking: the unit is Available again, the deal is Cancelled, and who and why are kept."""
	reason = squash(reason)
	if not reason:
		frappe.throw(_("Give the reason for cancelling the booking."))
	if not deal or not frappe.db.exists("Deal", deal):
		frappe.throw(_("There is no deal {0}.").format(deal), frappe.DoesNotExistError)
	doc = frappe.get_doc("Deal", deal)
	if doc.lead:
		_lead(doc.lead)  # the caller must be able to write the lead
	elif COMPANY_ADMIN not in frappe.get_roles():
		frappe.throw(_("You may not cancel this booking."), frappe.PermissionError)
	if not doc.unit:
		frappe.throw(_("This deal is not a booking of a unit."))
	frappe.db.savepoint(SAVEPOINT)
	try:
		row = holds._lock(doc.unit)
		doc.reload()
		if doc.deal_status == CANCELLED:
			frappe.throw(_("This booking is already cancelled."))
		if row.status != BOOKED:
			frappe.throw(
				_("Unit {0} is {1}, so its booking can not be cancelled here.").format(
					frappe.db.get_value("Unit", doc.unit, "unit_number"), row.status
				)
			)
		holds._change(doc.unit, AVAILABLE, _("Booking cancelled: {0}").format(reason))
		doc.flags.cancelling = True
		doc.flags.ignore_permissions = True
		doc.deal_status = CANCELLED
		doc.cancelled_by = frappe.session.user
		doc.cancelled_on = now_datetime()
		doc.cancellation_reason = reason
		doc.save()
	except Exception:
		frappe.db.rollback(save_point=SAVEPOINT)
		raise
	return {"deal": doc.name}


# --- what the lead screen shows ----------------------------------------------------------------------------


def _person(user) -> str:
	return holds._full_name(user)


def _deal_view(doc) -> dict:
	return {
		"name": doc.name,
		"unit": doc.unit or "",
		"unit_label": _unit_label(doc.unit) if doc.unit else "",
		"price": doc.price,
		"booking_amount": doc.booking_amount or 0,
		"cost_sheet": doc.cost_sheet or "",
		"deal_date": str(doc.deal_date or ""),
		"deal_status": doc.deal_status or ACTIVE,
		"approval_status": doc.approval_status,
		"booked_by_name": _person(doc.booked_by),
		"cancelled_by_name": _person(doc.cancelled_by),
		"cancelled_on": str(doc.cancelled_on or ""),
		"cancellation_reason": doc.cancellation_reason or "",
	}


def _bookable_units(lead) -> list[dict]:
	at = holds.now()
	units = []
	for row in frappe.get_all(
		"Unit",
		filters={"archived": 0, "status": ["in", [AVAILABLE, HELD]]},
		fields=["name", "status", "held_for_lead", "held_until", "configuration", "carpet_area"],
		order_by="project asc, unit_number asc",
		limit=300,
	):
		if row.status == HELD and not holds._lapsed(row, at) and row.held_for_lead != lead:
			continue
		units.append(
			{
				"name": row.name,
				"label": _unit_label(row.name),
				"status": AVAILABLE if holds._lapsed(row, at) else row.status,
				"configuration": row.configuration or "",
				"carpet_area": row.carpet_area,
				"cost_sheets": [
					{"name": s.name, "label": f"{s.name}: {s.plan_name or ''} {s.total or 0:,}".strip()}
					for s in frappe.get_list(
						"Cost Sheet",
						filters={"unit": row.name},
						fields=["name", "plan_name", "total"],
						order_by="creation desc",
						limit=20,
					)
				],
			}
		)
	return units


def panel(lead) -> dict:
	doc = _lead(lead, write=False)
	can_write = frappe.has_permission("Lead", "write", doc=lead)
	deals = [
		_deal_view(frappe.get_doc("Deal", name))
		for name in frappe.get_all("Deal", filters={"lead": lead}, pluck="name", order_by="creation desc")
	]
	view = consent.consent_view(lead)
	firm = _protected_partner(lead)
	return {
		"lead": lead,
		"stage": doc.stage,
		"can_book": bool(can_write and not doc.archived and (doc.get("pipeline") or "Buyer") == "Buyer"),
		"active": [d for d in deals if d["deal_status"] == ACTIVE],
		"cancelled": [d for d in deals if d["deal_status"] == CANCELLED],
		"units": _bookable_units(lead) if can_write else [],
		"partner": frappe.db.get_value("Channel Partner Firm", firm, "firm_name") if firm else "",
		"consent": {"status": view["status"], "warning": view["warning"], "message": view["message"]},
	}


# --- the whitelisted methods -----------------------------------------------------------------------------


@sellos_api(*BOOKERS)
def booking_panel(lead):
	"""The units the lead can be booked into, its bookings, the partner who would share the commission and the
	lead's consent warning."""
	return panel(lead)


@sellos_api(*BOOKERS)
def book_unit(lead, unit, price, booking_amount, cost_sheet=None):
	"""Book an Available unit, or one held for this lead: makes the Deal, marks the unit Booked and moves the
	lead to Booking, all or nothing."""
	result = book(lead, unit, price, booking_amount, cost_sheet)
	return {**result, **panel(lead)}


@sellos_api(*BOOKERS)
def cancel_booking(deal, reason):
	"""Cancel a booking with a reason. The lead's stage is left for the agent to choose."""
	lead = frappe.db.get_value("Deal", deal, "lead") if deal else None
	cancel(deal, reason)
	return panel(lead) if lead else {"deal": deal}
