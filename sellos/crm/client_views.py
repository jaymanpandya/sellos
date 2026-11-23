"""What a signed in Client sees of their own dealings (SOS-P5-05).

One read, `my_overview`, for the Client persona. It reads only the Client records whose email is the signed in
user's, and the leads, visits, deals and mandates that hang from them. Nothing else is reachable: no id of
another client's record is ever taken from the request.

* **Buyers** see their shortlists (SOS-P7-09's own list), their site visits and the status of their deals.
* **Sellers** see the status of their mandate and the enquiries on their property. The Dossier is listed only
  once the mandate is signed and not archived (SOS-P4-05's own rule, `mandates.is_released`).
* **Enquiries** are plain rows of exactly four fields (CLAUDE.md, "Client views"): a label (`Enquiry N`,
  numbered per property in the order the leads were created), the stage, when the lead reached that stage, and
  the response SLA badge. The rows are the Buyer pipeline leads whose `Lead.property` is the property of the
  seller's own Seller lead, never the seller's own lead. There is no name, phone, email, message, source,
  consent status or agent note, and no lead, client or property id. Outside SLA means the lead has at least
  one Response Alert (SOS-P7-13), resolved or not. There is no per stage SLA.
"""

import frappe

from sellos.access.registry import sellos_api
from sellos.access.roles import CLIENT
from sellos.inventory import mandates
from sellos.inventory.shortlists import my_clients, my_shortlists

IN_SLA = "In SLA"
OUTSIDE_SLA = "Outside SLA"
ROW_FIELDS = ("label", "stage", "stage_on", "sla")
BUYER, SELLER = "Buyer", "Seller"


def _stage_label(stage) -> str:
	return (frappe.db.get_value("Pipeline Stage", stage, "stage_name") if stage else "") or stage or ""


def _stage_times(leads) -> dict:
	"""For each lead, when it reached its current stage: the newest log row for that stage, else its creation."""
	times = {lead.name: lead.creation for lead in leads}
	if not leads:
		return times
	rows = frappe.get_all(
		"Lead Stage Change",
		filters={"parent": ["in", [lead.name for lead in leads]], "parenttype": "Lead"},
		fields=["parent", "to_stage", "changed_on"],
		order_by="changed_on asc, idx asc",
	)
	stage = {lead.name: lead.stage for lead in leads}
	for row in rows:
		if row.to_stage == stage[row.parent]:
			times[row.parent] = row.changed_on
	return times


def enquiry_rows(property_name) -> list[dict]:
	"""The enquiries on one property: its Buyer pipeline leads, oldest first, as four plain fields each."""
	leads = frappe.get_all(
		"Lead",
		filters={"property": property_name, "pipeline": BUYER, "archived": 0},
		fields=["name", "stage", "creation"],
		order_by="creation asc, name asc",
	)
	times = _stage_times(leads)
	alerted = set(
		frappe.get_all(
			"Response Alert", filters={"lead": ["in", [x.name for x in leads] or [""]]}, pluck="lead"
		)
	)
	return [
		{
			"label": f"Enquiry {number}",
			"stage": _stage_label(lead.stage),
			"stage_on": str(times[lead.name]),
			"sla": OUTSIDE_SLA if lead.name in alerted else IN_SLA,
		}
		for number, lead in enumerate(leads, start=1)
	]


def _mandate_view(lead) -> dict | None:
	row = frappe.get_all(
		"Mandate",
		filters={"lead": lead, "archived": 0},
		fields=["name"],
		order_by="creation desc",
		limit=1,
	)
	if not row:
		return None
	doc = frappe.get_doc("Mandate", row[0].name)
	released = mandates.is_released(doc)
	view = {
		"type": doc.mandate_type,
		"status": doc.status,
		"term_months": doc.term_months,
		"starts_on": str(doc.start_date or ""),
		"ends_on": str(doc.ends_on or ""),
		"dossier_released": released,
		"dossier": [],
	}
	if released:  # titles only: the notes and files stay with the agent
		view["dossier"] = [{"kind": i.kind, "title": i.title} for i in doc.dossier]
	return view


def _seller_views(clients) -> list[dict]:
	leads = frappe.get_all(
		"Lead",
		filters={"client": ["in", clients], "pipeline": SELLER, "archived": 0},
		fields=["name", "stage", "property"],
		order_by="creation asc, name asc",
	)
	views = []
	for lead in leads:
		views.append(
			{
				"stage": _stage_label(lead.stage),
				"property": frappe.db.get_value("Property", lead.property, "title") if lead.property else "",
				"has_property": bool(lead.property),
				"mandate": _mandate_view(lead.name),
				"enquiries": enquiry_rows(lead.property) if lead.property else [],
			}
		)
	return views


def _visit_rows(leads) -> list[dict]:
	rows = frappe.get_all(
		"Site Visit",
		filters={"lead": ["in", leads or [""]], "archived": 0},
		fields=["project_name", "visit_datetime", "status", "confirmation_status"],
		order_by="visit_datetime desc",
	)
	return [
		{
			"project": r.project_name or "",
			"when": str(r.visit_datetime or ""),
			"status": r.status,
			"confirmation": r.confirmation_status or "",
		}
		for r in rows
	]


def _deal_rows(clients) -> list[dict]:
	rows = frappe.get_all(
		"Deal",
		filters={"client": ["in", clients], "archived": 0},
		fields=["property", "unit", "deal_date", "deal_status", "approval_status"],
		order_by="deal_date desc, creation desc",
	)
	out = []
	for r in rows:
		target = ""
		if r.property:
			target = frappe.db.get_value("Property", r.property, "title") or ""
		elif r.unit:
			target = frappe.db.get_value("Unit", r.unit, "unit_number") or ""
		out.append(
			{
				"target": target,
				"deal_date": str(r.deal_date or ""),
				"status": "Cancelled" if r.deal_status == "Cancelled" else "Booked",
			}
		)
	return out


def _buyer_view(clients) -> dict:
	leads = frappe.get_all(
		"Lead",
		filters={"client": ["in", clients], "pipeline": BUYER, "archived": 0},
		fields=["name", "stage", "creation"],
		order_by="creation asc",
	)
	times = _stage_times(leads)
	return {
		"stages": [{"stage": _stage_label(x.stage), "stage_on": str(times[x.name])} for x in leads],
		"visits": _visit_rows([x.name for x in leads]),
		"deals": _deal_rows(clients),
	}


@sellos_api(CLIENT)
def my_overview():
	"""The signed in Client's own shortlists, visits, deal status, mandate status and enquiries. Only the Client
	records with their email are read; the request names nothing."""
	clients = my_clients()
	if not clients:
		return {"buyer": {"stages": [], "visits": [], "deals": []}, "shortlists": [], "sellers": []}
	return {
		"buyer": _buyer_view(clients),
		"shortlists": my_shortlists()["shortlists"],
		"sellers": _seller_views(clients),
	}
