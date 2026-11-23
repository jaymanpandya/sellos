"""Deals and their commission split in the web app (SOS-P4-06).

A deal links a client to a unit or a property at a price. Its commission is split among the agent, the channel
partner firm and the company: the percents add up to exactly 100, every party is named once, and a channel partner
share needs an approved firm. Only a Company Admin records a deal, approves its split, reopens an approved split
and archives a deal. An Agent, a Sales Manager, a Client, a Channel Partner and the Platform Admin hold no deal
method. Every call saves through the Deal DocType, so its checks run on every call. Nothing is deleted.
"""

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN
from sellos.sellos.doctype.channel_partner_firm.channel_partner_firm import APPROVED as FIRM_APPROVED
from sellos.sellos.doctype.deal.deal import APPROVED, PARTIES, PENDING

# What a caller may set on a deal. The approval and the archive are never in this list.
FIELDS = ("client", "lead", "unit", "property", "price", "deal_date", "commission_amount")
SPLIT_FIELDS = ("party_type", "agent", "partner_firm", "percent")


def _values(values) -> dict:
	return frappe.parse_json(values) if isinstance(values, str) else (values or {})


def _flag(value) -> bool:
	return str(value).lower() in ("1", "true", "yes")


def _deal(name, write=False):
	if not name or not frappe.db.exists("Deal", name):
		frappe.throw(_("There is no deal {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Deal", name)
	doc.check_permission("write" if write else "read")
	if write and doc.archived:
		frappe.throw(_("An archived deal can not be changed."))
	return doc


def _people() -> dict:
	return {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}


def _firms() -> dict:
	return {f.name: f.firm_name for f in frappe.get_all("Channel Partner Firm", fields=["name", "firm_name"])}


def _target(doc) -> str:
	if doc.unit:
		project, number = frappe.db.get_value("Unit", doc.unit, ["project", "unit_number"])
		name = frappe.db.get_value("Project", project, "project_name") or project
		return f"{name} {number}"
	return frappe.db.get_value("Property", doc.property, "title") or doc.property


def _row(doc, people, firms) -> dict:
	return {
		"name": doc.name,
		"client": doc.client,
		"client_name": frappe.db.get_value("Client", doc.client, "client_name") or doc.client,
		"lead": doc.lead or "",
		"unit": doc.unit or "",
		"property": doc.property or "",
		"target": _target(doc),
		"price": doc.price,
		"deal_date": str(doc.deal_date or ""),
		"commission_amount": doc.commission_amount,
		"approval_status": doc.approval_status,
		"approved_by_name": people.get(doc.approved_by, doc.approved_by or ""),
		"approved_on": str(doc.approved_on or ""),
		"archived": int(doc.archived or 0),
		"splits": [
			{
				"party_type": s.party_type,
				"party": firms.get(s.partner_firm, s.partner_firm)
				if s.party_type == "Channel Partner"
				else people.get(s.agent, s.agent)
				if s.party_type == "Agent"
				else _("The company"),
				"agent": s.agent or "",
				"partner_firm": s.partner_firm or "",
				"percent": s.percent,
				"amount": s.amount,
			}
			for s in doc.splits
		],
	}


def _options() -> dict:
	agents = frappe.get_all("Has Role", filters={"role": AGENT, "parenttype": "User"}, pluck="parent")
	people = _people()
	return {
		"clients": [
			{"value": c.name, "label": c.client_name or c.name}
			for c in frappe.get_list(
				"Client",
				filters={"archived": 0},
				fields=["name", "client_name"],
				limit=500,
				order_by="client_name asc",
			)
		],
		"units": [
			{"value": u.name, "label": f"{u.project} {u.unit_number}"}
			for u in frappe.get_all(
				"Unit",
				filters={"archived": 0},
				fields=["name", "project", "unit_number"],
				limit=500,
			)
		],
		"properties": [
			{"value": p.name, "label": p.title or p.name}
			for p in frappe.get_all("Property", filters={"archived": 0}, fields=["name", "title"], limit=500)
		],
		"agents": [{"value": a, "label": people.get(a, a)} for a in sorted(set(agents)) if a in people],
		"firms": [
			{"value": f.name, "label": f.firm_name}
			for f in frappe.get_all(
				"Channel Partner Firm", filters={"status": FIRM_APPROVED}, fields=["name", "firm_name"]
			)
		],
		"party_types": list(PARTIES),
	}


def _overview(include_archived=False) -> dict:
	filters = {} if include_archived else {"archived": 0}
	people, firms = _people(), _firms()
	names = frappe.get_list("Deal", filters=filters, pluck="name", order_by="creation desc")
	return {"deals": [_row(frappe.get_doc("Deal", n), people, firms) for n in names], **_options()}


@sellos_api(COMPANY_ADMIN)
def deal_overview(include_archived=0):
	"""The deals with their commission splits, and what a deal and a split can be made from: the clients, units,
	properties, agents and approved channel partner firms."""
	return _overview(_flag(include_archived))


@sellos_api(COMPANY_ADMIN)
def save_deal(values, name=None):
	"""Record a deal with its commission split (a list of {party_type, agent, partner_firm, percent}, adding up to
	100), or correct one whose split is not approved. A saved deal always waits for approval: this call never
	approves."""
	values = _values(values)
	splits = [{k: s.get(k) for k in SPLIT_FIELDS if k in s} for s in values.get("splits") or []]
	if name:
		doc = _deal(name, write=True)
		for field in FIELDS:
			if field in values:
				doc.set(field, values[field])
		if "splits" in values:
			doc.set("splits", splits)
		doc.save()
	else:
		data = {k: values[k] for k in FIELDS if k in values}
		doc = frappe.get_doc({"doctype": "Deal", **data, "splits": splits, "approval_status": PENDING})
		doc.insert()
	return {"name": doc.name, **_overview()}


@sellos_api(COMPANY_ADMIN)
def approve_splits(name):
	"""Approve the commission split of a deal. It is refused unless the split adds up to 100 percent, and who
	approved it and when is kept."""
	doc = _deal(name, write=True)
	if doc.approval_status == APPROVED:
		frappe.throw(_("This split is already approved."))
	doc.approve()
	doc.save()
	return {"name": doc.name, **_overview()}


@sellos_api(COMPANY_ADMIN)
def reopen_splits(name):
	"""Take an approved split back to Pending approval so it can be corrected. The change is logged."""
	doc = _deal(name, write=True)
	if doc.approval_status != APPROVED:
		frappe.throw(_("Only an approved split is reopened."))
	doc.approval_status = PENDING
	doc.save()
	return {"name": doc.name, **_overview()}


@sellos_api(COMPANY_ADMIN)
def set_deal_archived(name, archived=1):
	"""Archive a deal, or restore it. Nothing is deleted."""
	doc = _deal(name)
	doc.check_permission("write")
	doc.archived = 1 if _flag(archived) else 0
	doc.save()
	return {"name": doc.name, **_overview()}
