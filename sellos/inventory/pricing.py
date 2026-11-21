"""Price lists, payment plans and the cost of a unit (SOS-P7-07).

* A project has dated price lists: a base rate per square foot of carpet area, a floor rise per square foot
  for every floor above a set floor, and charges (preferred location, parking, other), each an amount or a rate
  per square foot. The list in force is the latest one whose date has come; earlier ones are kept. A list is
  never changed once made: a new list with a later date takes over.
* A payment plan template (construction linked, time linked or down payment) lists instalments as percentages
  that add up to 100.
* The company's stamp duty, registration and GST percentages are company settings a Company Admin sets.
* Every amount is in whole rupees, each rounded half up on its own: the base price, the floor rise, each
  charge, then stamp duty, registration and GST on the agreement value, then the total. A parking amount is per
  parking slot of the unit.
* `cost_breakdown` is the one place the arithmetic is done, with exact decimals and no database.
"""

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER

SETTINGS = "SellOS Settings"
READERS = (COMPANY_ADMIN, AGENT, SALES_MANAGER)
CHARGE_TYPES = ("Preferred location", "Parking", "Other")
BASES = ("Amount", "Rate per sq ft")
PLAN_TYPES = ("Construction linked", "Time linked", "Down payment")
RATE_FIELDS = ("stamp_duty_percent", "registration_percent", "gst_percent")
HUNDRED = Decimal(100)


def today():
	"""The date. A test replaces it to fix the day."""
	return getdate(nowdate())


def _d(value) -> Decimal:
	return Decimal(str(value or 0))


def rupees(value) -> int:
	"""A whole number of rupees, rounded half up."""
	return int(_d(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def charge_amount(charge, carpet_area, parking) -> int:
	"""One charge in rupees: its amount (per parking slot for parking), or its rate times the carpet area."""
	if charge["basis"] == "Rate per sq ft":
		return rupees(_d(charge["value"]) * _d(carpet_area))
	slots = _d(parking) if charge["charge_type"] == "Parking" else Decimal(1)
	return rupees(_d(charge["value"]) * slots)


def cost_breakdown(
	*,
	carpet_area,
	floor,
	parking,
	base_rate,
	floor_rise_rate,
	floor_rise_from_floor,
	charges,
	stamp_duty_percent,
	registration_percent,
	gst_percent,
) -> dict:
	"""The price of a unit. `charges` are the ones that apply (dicts with charge_type, charge_name, basis,
	value). Returns whole rupees: base_price, floor_rise_amount, charges (each with its amount), charges_total,
	agreement_value, stamp_duty, registration, gst and total."""
	area = _d(carpet_area)
	base_price = rupees(_d(base_rate) * area)
	floors_above = max(0, int(floor or 0) - int(floor_rise_from_floor or 0)) if floor is not None else 0
	floor_rise = rupees(_d(floor_rise_rate) * floors_above * area)
	lines = [{**c, "amount": charge_amount(c, carpet_area, parking)} for c in charges]
	charges_total = sum(line["amount"] for line in lines)
	agreement_value = base_price + floor_rise + charges_total

	def on_agreement(percent):
		return rupees(_d(agreement_value) * _d(percent) / HUNDRED)

	stamp_duty = on_agreement(stamp_duty_percent)
	registration = on_agreement(registration_percent)
	gst = on_agreement(gst_percent)
	return {
		"base_price": base_price,
		"floor_rise_amount": floor_rise,
		"floors_above": floors_above,
		"charges": lines,
		"charges_total": charges_total,
		"agreement_value": agreement_value,
		"stamp_duty": stamp_duty,
		"registration": registration,
		"gst": gst,
		"total": agreement_value + stamp_duty + registration + gst,
	}


def payment_schedule(instalments, total) -> list[dict]:
	"""The instalments of a plan in rupees. Each is its percent of the total, rounded; the last takes what is
	left, so the schedule always adds up to the total."""
	rows, paid = [], 0
	for number, row in enumerate(instalments, start=1):
		amount = (
			total - paid if number == len(instalments) else rupees(_d(total) * _d(row["percent"]) / HUNDRED)
		)
		paid += amount
		rows.append({**row, "amount": amount})
	return rows


# --- records ----------------------------------------------------------------------------------


def price_list_in_force(project, on=None):
	"""The project's price list in force on a day (today by default), or None."""
	names = frappe.get_all(
		"Price List",
		filters={"project": project, "effective_from": ["<=", getdate(on) if on else today()]},
		order_by="effective_from desc, creation desc",
		pluck="name",
		limit=1,
	)
	return frappe.get_doc("Price List", names[0]) if names else None


def cost_rates() -> dict | None:
	"""The company's stamp duty, registration and GST percentages, or None until a Company Admin saves them."""
	if not frappe.db.get_single_value(SETTINGS, "cost_rates_saved"):
		return None
	return {key: float(frappe.db.get_single_value(SETTINGS, key) or 0) for key in RATE_FIELDS}


def _project(name):
	if not name or not frappe.db.exists("Project", name):
		frappe.throw(_("There is no project {0}.").format(name), frappe.DoesNotExistError)
	return frappe.get_doc("Project", name)


def _values(values) -> dict:
	return frappe.parse_json(values) if isinstance(values, str) else (values or {})


def price_list_view(doc, in_force=False) -> dict:
	return {
		"name": doc.name,
		"title": doc.title,
		"effective_from": str(doc.effective_from),
		"base_rate": doc.base_rate,
		"floor_rise_rate": doc.floor_rise_rate,
		"floor_rise_from_floor": doc.floor_rise_from_floor,
		"in_force": in_force,
		"scheduled": getdate(doc.effective_from) > today(),
		"charges": [
			{
				"charge_type": row.charge_type,
				"charge_name": row.charge_name,
				"basis": row.basis,
				"value": row.value,
				"always_apply": cint(row.always_apply),
			}
			for row in doc.charges
		],
	}


def plan_view(doc) -> dict:
	return {
		"name": doc.name,
		"plan_name": doc.plan_name,
		"plan_type": doc.plan_type,
		"archived": cint(doc.archived),
		"instalments": [
			{
				"label": row.label,
				"due_on": row.due_on or "",
				"days_after_booking": row.days_after_booking or 0,
				"percent": row.percent,
			}
			for row in doc.instalments
		],
	}


def project_pricing_state(project) -> dict:
	forced = price_list_in_force(project)
	lists = [
		price_list_view(frappe.get_doc("Price List", name), in_force=bool(forced and forced.name == name))
		for name in frappe.get_list(
			"Price List", filters={"project": project}, order_by="effective_from desc", pluck="name"
		)
	]
	plans = [
		plan_view(frappe.get_doc("Payment Plan", name))
		for name in frappe.get_list(
			"Payment Plan", filters={"project": project}, order_by="creation asc", pluck="name"
		)
	]
	return {
		"project": project,
		"price_lists": lists,
		"payment_plans": plans,
		"rates": cost_rates(),
		"can_edit": COMPANY_ADMIN in frappe.get_roles(),
		"charge_types": list(CHARGE_TYPES),
		"bases": list(BASES),
		"plan_types": list(PLAN_TYPES),
	}


@sellos_api(*READERS)
def project_pricing(project):
	"""A project's price lists (the one in force marked), its payment plans and the company's percentages."""
	_project(project).check_permission("read")
	return project_pricing_state(project)


@sellos_api(COMPANY_ADMIN)
def save_price_list(project, values):
	"""Make a dated price list for a project. It is never changed afterwards: a new list takes over on its date."""
	_project(project)
	values = _values(values)
	charges = [
		{key: row.get(key) for key in ("charge_type", "charge_name", "basis", "value", "always_apply")}
		for row in values.get("charges") or []
	]
	doc = frappe.get_doc(
		{
			"doctype": "Price List",
			"project": project,
			"title": values.get("title"),
			"effective_from": values.get("effective_from"),
			"base_rate": values.get("base_rate"),
			"floor_rise_rate": values.get("floor_rise_rate") or 0,
			"floor_rise_from_floor": values.get("floor_rise_from_floor") or 0,
			"charges": charges,
		}
	)
	doc.insert()
	return {"name": doc.name, **project_pricing_state(project)}


@sellos_api(COMPANY_ADMIN)
def save_payment_plan(project, values, name=None):
	"""Make a payment plan template for a project, or correct one. The instalments must add up to 100 percent.
	A cost sheet already made keeps the schedule it was made with."""
	_project(project)
	values = _values(values)
	instalments = [
		{key: row.get(key) for key in ("label", "due_on", "days_after_booking", "percent")}
		for row in values.get("instalments") or []
	]
	if name:
		doc = frappe.get_doc("Payment Plan", name)
		doc.check_permission("write")
		if doc.project != project:
			frappe.throw(_("That payment plan belongs to another project."))
		for key in ("plan_name", "plan_type"):
			if key in values:
				doc.set(key, values[key])
		doc.set("instalments", instalments)
		doc.save()
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Payment Plan",
				"project": project,
				"plan_name": values.get("plan_name"),
				"plan_type": values.get("plan_type"),
				"instalments": instalments,
			}
		)
		doc.insert()
	return {"name": doc.name, **project_pricing_state(project)}


@sellos_api(COMPANY_ADMIN)
def archive_payment_plan(name, archived=1):
	"""Archive a payment plan, or restore it. Nothing is deleted."""
	doc = frappe.get_doc("Payment Plan", name)
	doc.check_permission("write")
	doc.archived = 1 if str(archived).lower() in ("1", "true", "yes") else 0
	doc.save()
	return {"name": doc.name, **project_pricing_state(doc.project)}


@sellos_api(COMPANY_ADMIN)
def save_cost_settings(stamp_duty_percent, registration_percent, gst_percent):
	"""Set the stamp duty, registration and GST percentages that new cost sheets use. A cost sheet already made
	keeps the percentages it used."""
	saved = {}
	for key, value in zip(RATE_FIELDS, (stamp_duty_percent, registration_percent, gst_percent), strict=True):
		try:
			number = Decimal(str(value).strip())
		except ArithmeticError:
			number = Decimal(-1)
		if not number.is_finite() or not 0 <= number <= 100:
			frappe.throw(_("Enter each percentage from 0 to 100."))
		saved[key] = float(number)
	for key, value in saved.items():
		frappe.db.set_single_value(SETTINGS, key, value)
	frappe.db.set_single_value(SETTINGS, "cost_rates_saved", 1)
	return {"rates": cost_rates()}
