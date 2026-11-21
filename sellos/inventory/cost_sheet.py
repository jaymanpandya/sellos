"""Cost sheets (SOS-P7-07).

An Agent or a Company Admin makes a cost sheet from a unit: the price from the price list in force, the charges
that apply, stamp duty, registration and GST at the company's percentages, the total, and the schedule of a
chosen payment plan. The sheet keeps the price list, the rates and the percentages it used, so a later change
to any of them never alters a sheet already made. A sheet is never changed and never deleted. An Agent sees
the sheets they made; a Company Admin sees them all; a Sales Manager sees none. The sheet is shown on screen
and as a PDF with the company's branding.
"""

import base64
import mimetypes
import re

import frappe
from frappe import _
from frappe.utils import cint, escape_html, format_datetime, get_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN
from sellos.inventory import pricing

SETTINGS = "SellOS Settings"
EDITORS = (COMPANY_ADMIN, AGENT)
DEFAULT_COLOUR = "#1F3A5F"
_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
SNAPSHOT = (
	"unit",
	"project",
	"unit_number",
	"configuration",
	"carpet_area",
	"floor",
	"parking",
	"price_list",
	"price_list_title",
	"price_list_from",
	"base_rate",
	"floor_rise_rate",
	"floor_rise_from_floor",
	"stamp_duty_percent",
	"registration_percent",
	"gst_percent",
	"base_price",
	"floor_rise_amount",
	"charges_total",
	"agreement_value",
	"stamp_duty",
	"registration",
	"gst",
	"total",
	"payment_plan",
	"plan_name",
	"plan_type",
)


def _unit(name):
	if not name or not frappe.db.exists("Unit", name):
		frappe.throw(_("There is no unit {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Unit", name)
	doc.check_permission("read")
	return doc


def _charges_view(rows) -> list[dict]:
	return [
		{
			"charge_type": row.charge_type,
			"charge_name": row.charge_name,
			"basis": row.basis,
			"value": row.value,
			"always_apply": 1 if row.always_apply else 0,
		}
		for row in rows
	]


def _active_plans(project) -> list:
	return [
		pricing.plan_view(frappe.get_doc("Payment Plan", name))
		for name in frappe.get_list(
			"Payment Plan", filters={"project": project, "archived": 0}, order_by="creation asc", pluck="name"
		)
	]


@sellos_api(*EDITORS)
def cost_sheet_options(unit):
	"""What a cost sheet of this unit needs chosen: the price list in force, which of its charges are the
	agent's to choose, and the payment plans. `ready` is False, with the reason, until the project has a price
	list in force and the company's percentages are set."""
	doc = _unit(unit)
	forced = pricing.price_list_in_force(doc.project)
	rates = pricing.cost_rates()
	problem = ""
	if not forced:
		problem = _("This project has no price list in force. A Company Admin adds one on the project page.")
	elif rates is None:
		problem = _(
			"The stamp duty, registration and GST percentages are not set. A Company Admin sets them on the project page."
		)
	return {
		"unit": {
			"name": doc.name,
			"unit_number": doc.unit_number,
			"project": doc.project,
			"project_name": frappe.db.get_value("Project", doc.project, "project_name"),
			"configuration": doc.configuration or "",
			"carpet_area": doc.carpet_area,
			"floor": doc.floor,
			"parking": doc.parking or 0,
			"status": doc.status,
		},
		"ready": not problem,
		"problem": problem,
		"price_list": pricing.price_list_view(forced, in_force=True) if forced else None,
		"rates": rates,
		"plans": _active_plans(doc.project),
		"sheets": _sheet_rows(doc.name),
	}


def _sheet_rows(unit) -> list[dict]:
	rows = frappe.get_list(
		"Cost Sheet",
		filters={"unit": unit},
		fields=["name", "total", "plan_name", "price_list_title", "owner", "creation"],
		order_by="creation desc",
	)
	people = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	return [
		{
			"name": row.name,
			"total": row.total,
			"plan_name": row.plan_name,
			"price_list_title": row.price_list_title,
			"made_by": people.get(row.owner, row.owner),
			"made_on": str(row.creation),
		}
		for row in rows
	]


def build_values(unit_doc, plan, optional_charges, at=None) -> dict:
	"""Everything a cost sheet of this unit keeps, worked out from the price list in force, the company's
	percentages and the plan. Nothing is saved."""
	forced = pricing.price_list_in_force(unit_doc.project, at)
	if not forced:
		frappe.throw(
			_("This project has no price list in force. A Company Admin adds one on the project page.")
		)
	rates = pricing.cost_rates()
	if rates is None:
		frappe.throw(
			_(
				"The stamp duty, registration and GST percentages are not set. A Company Admin sets them on the project page."
			)
		)
	chosen = {str(name) for name in (optional_charges or [])}
	known = {row.charge_name for row in forced.charges if not row.always_apply}
	if chosen - known:
		frappe.throw(
			_("{0} is not a charge you can choose on this price list.").format(
				", ".join(sorted(chosen - known))
			)
		)
	applied = [
		row for row in _charges_view(forced.charges) if row["always_apply"] or row["charge_name"] in chosen
	]
	figures = pricing.cost_breakdown(
		carpet_area=unit_doc.carpet_area,
		floor=unit_doc.floor,
		parking=unit_doc.parking,
		base_rate=forced.base_rate,
		floor_rise_rate=forced.floor_rise_rate,
		floor_rise_from_floor=forced.floor_rise_from_floor,
		charges=applied,
		**rates,
	)
	schedule = pricing.payment_schedule(plan["instalments"], figures["total"])
	return {
		"unit": unit_doc.name,
		"project": unit_doc.project,
		"unit_number": unit_doc.unit_number,
		"configuration": unit_doc.configuration or "",
		"carpet_area": unit_doc.carpet_area,
		"floor": unit_doc.floor,
		"parking": unit_doc.parking or 0,
		"price_list": forced.name,
		"price_list_title": forced.title,
		"price_list_from": forced.effective_from,
		"base_rate": forced.base_rate,
		"floor_rise_rate": forced.floor_rise_rate,
		"floor_rise_from_floor": forced.floor_rise_from_floor,
		**rates,
		**{
			key: figures[key]
			for key in (
				"base_price",
				"floor_rise_amount",
				"charges_total",
				"agreement_value",
				"stamp_duty",
				"registration",
				"gst",
				"total",
			)
		},
		"payment_plan": plan["name"],
		"plan_name": plan["plan_name"],
		"plan_type": plan["plan_type"],
		"charges": [
			{key: line[key] for key in ("charge_type", "charge_name", "basis", "value", "amount")}
			for line in figures["charges"]
		],
		"instalments": [
			{key: line[key] for key in ("label", "due_on", "percent", "amount")} for line in schedule
		],
	}


@sellos_api(*EDITORS)
def make_cost_sheet(unit, payment_plan, optional_charges=None):
	"""Make a cost sheet of a unit with a payment plan of its project. `optional_charges` names the charges
	of the price list the agent chooses to add; always applying charges and parking go on every sheet."""
	doc = _unit(unit)
	if doc.archived:
		frappe.throw(_("Unit {0} is archived. Restore it first.").format(doc.unit_number))
	if isinstance(optional_charges, str):
		optional_charges = frappe.parse_json(optional_charges) if optional_charges.strip() else []
	if not payment_plan or not frappe.db.exists("Payment Plan", payment_plan):
		frappe.throw(_("Choose a payment plan."))
	plan = frappe.get_doc("Payment Plan", payment_plan)
	if plan.project != doc.project or plan.archived:
		frappe.throw(_("Choose a payment plan of this project that is not archived."))
	values = build_values(doc, pricing.plan_view(plan), optional_charges)
	sheet = frappe.get_doc({"doctype": "Cost Sheet", **values})
	sheet.insert()
	return get_cost_sheet(sheet.name)


@sellos_api(*EDITORS)
def unit_cost_sheets(unit):
	"""The cost sheets of a unit that the caller may see, newest first."""
	return {"unit": _unit(unit).name, "sheets": _sheet_rows(unit)}


def _brand() -> dict:
	fields = ("company_name", "logo", "brand_color", "contact_phone", "contact_email", "address")
	row = frappe._dict({field: frappe.db.get_single_value(SETTINGS, field) for field in fields})
	colour = row.get("brand_color") or ""
	return {
		"name": row.get("company_name") or "SellOS",
		"logo": row.get("logo") or "",
		"colour": colour if _COLOUR.match(colour) else DEFAULT_COLOUR,
		"phone": row.get("contact_phone") or "",
		"email": row.get("contact_email") or "",
		"address": row.get("address") or "",
	}


def sheet_view(doc) -> dict:
	view = {key: doc.get(key) for key in SNAPSHOT}
	view.update(
		{
			"name": doc.name,
			"price_list_from": str(doc.price_list_from or ""),
			"project_name": frappe.db.get_value("Project", doc.project, "project_name") or doc.project,
			"made_on": str(doc.creation),
			"made_by": frappe.db.get_value("User", doc.owner, "full_name") or doc.owner,
			"charges": [
				{
					"charge_type": row.charge_type,
					"charge_name": row.charge_name,
					"basis": row.basis,
					"value": row.value,
					"amount": cint(row.amount),
				}
				for row in doc.charges
			],
			"instalments": [
				{
					"label": row.label,
					"due_on": row.due_on or "",
					"percent": row.percent,
					"amount": cint(row.amount),
				}
				for row in doc.instalments
			],
			"brand": _brand(),
		}
	)
	for key in (
		"base_price",
		"floor_rise_amount",
		"charges_total",
		"agreement_value",
		"stamp_duty",
		"registration",
		"gst",
		"total",
	):
		view[key] = cint(view[key])
	return view


def _sheet(name):
	if not name or not frappe.db.exists("Cost Sheet", name):
		frappe.throw(_("There is no cost sheet {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Cost Sheet", name)
	doc.check_permission("read")
	return doc


@sellos_api(*EDITORS)
def get_cost_sheet(name):
	"""One cost sheet as it was issued, with the company's branding."""
	return sheet_view(_sheet(name))


# --- the PDF ------------------------------------------------------------------------------------


def inr(amount) -> str:
	"""Rupees with Indian grouping: 10155600 is Rs 1,01,55,600."""
	digits = str(abs(int(amount)))
	head, tail = digits[:-3], digits[-3:]
	groups = []
	while len(head) > 2:
		groups.insert(0, head[-2:])
		head = head[:-2]
	if head:
		groups.insert(0, head)
	text = ",".join([*groups, tail])
	return f"{'-' if amount < 0 else ''}Rs {text}"


def _logo_data_uri(url) -> str:
	if not url or not frappe.db.exists("File", {"file_url": url}):
		return ""
	content = frappe.get_doc("File", {"file_url": url}).get_content()
	if isinstance(content, str):
		content = content.encode()
	mime = mimetypes.guess_type(url)[0] or "image/png"
	return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def sheet_html(view) -> str:
	"""The cost sheet as one HTML page, in the company's colour with its logo, name and contact details."""
	e = escape_html
	brand = view["brand"]
	logo = _logo_data_uri(brand["logo"])
	contact = " | ".join(part for part in (brand["phone"], brand["email"]) if part)
	made = format_datetime(get_datetime(view["made_on"]), "dd MMM yyyy")

	def row(label, amount, bold=False):
		style = ' class="strong"' if bold else ""
		return f'<tr{style}><td>{e(label)}</td><td class="num">{e(inr(amount))}</td></tr>'

	price_rows = [
		row(
			_("Base price ({0} sq ft at {1} per sq ft)").format(view["carpet_area"], inr(view["base_rate"])),
			view["base_price"],
		)
	]
	if view["floor_rise_amount"]:
		price_rows.append(row(_("Floor rise (floor {0})").format(view["floor"]), view["floor_rise_amount"]))
	price_rows += [row(c["charge_name"], c["amount"]) for c in view["charges"]]
	price_rows += [
		row(_("Agreement value"), view["agreement_value"], True),
		row(_("Stamp duty ({0}%)").format(view["stamp_duty_percent"]), view["stamp_duty"]),
		row(_("Registration ({0}%)").format(view["registration_percent"]), view["registration"]),
		row(_("GST ({0}%)").format(view["gst_percent"]), view["gst"]),
		row(_("Total"), view["total"], True),
	]

	def instalment(i):
		cells = (e(i["label"]), e(i["due_on"]), e(f"{i['percent']}%"), e(inr(i["amount"])))
		return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"

	schedule = "".join(instalment(i) for i in view["instalments"])
	return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body {{ font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #222; }}
.head {{ border-bottom: 3px solid {brand["colour"]}; padding-bottom: 8px; margin-bottom: 14px; }}
.head img {{ height: 48px; vertical-align: middle; margin-right: 12px; }}
.head .name {{ font-size: 20px; font-weight: bold; color: {brand["colour"]}; vertical-align: middle; }}
.small {{ color: #555; font-size: 11px; }}
h2 {{ font-size: 14px; color: {brand["colour"]}; margin: 18px 0 6px; }}
table {{ width: 100%; border-collapse: collapse; }}
td, th {{ padding: 5px 6px; border-bottom: 1px solid #ddd; text-align: left; }}
th {{ background: {brand["colour"]}; color: #fff; }}
.num {{ text-align: right; }}
.strong td {{ font-weight: bold; background: #f3f3f3; }}
</style></head><body>
<div class="head">{f'<img src="{logo}">' if logo else ""}<span class="name">{e(brand["name"])}</span>
<div class="small">{e(contact)}</div><div class="small">{e(brand["address"])}</div></div>
<h1 style="font-size:16px">{e(_("Cost sheet"))} {e(view["name"])}</h1>
<p>{e(view["project_name"])} &ndash; {e(_("Unit"))} {e(view["unit_number"])}, {e(view["configuration"])},
{e(str(view["carpet_area"]))} {e(_("sq ft carpet area"))}, {e(_("floor"))} {e(str(view["floor"] if view["floor"] is not None else "-"))},
{e(str(view["parking"]))} {e(_("parking"))}.<br>
<span class="small">{e(_("Price list"))}: {e(view["price_list_title"])} ({e(_("in force from"))} {e(view["price_list_from"])}).
{e(_("Made on"))} {e(made)} {e(_("by"))} {e(view["made_by"])}.</span></p>
<h2>{e(_("Price"))}</h2><table>{"".join(price_rows)}</table>
<h2>{e(_("Payment plan"))}: {e(view["plan_name"])} ({e(view["plan_type"])})</h2>
<table><tr><th>{e(_("Instalment"))}</th><th>{e(_("Due on"))}</th><th class="num">{e(_("Percent"))}</th><th class="num">{e(_("Amount"))}</th></tr>{schedule}</table>
<p class="small">{e(_("Amounts are in rupees, rounded to the rupee. Stamp duty, registration and GST are worked on the agreement value."))}</p>
</body></html>"""


@sellos_api(*EDITORS)
def cost_sheet_pdf(name):
	"""The cost sheet as a PDF with the company's branding, shown by the browser."""
	from frappe.utils.pdf import get_pdf

	from sellos.inventory.plain_pdf import build_pdf

	doc = _sheet(name)
	view = sheet_view(doc)
	try:
		content = get_pdf(sheet_html(view))
	except OSError:
		# The page layout program is not installed on this machine: write the figures plainly instead.
		content = build_pdf(view, inr)
	frappe.local.response.filename = f"{doc.name}.pdf"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "pdf"
