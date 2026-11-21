"""Share projects, units and collateral with channel partners (SOS-P7-03).

A Company Admin shares a project with one Approved partner firm, several, or every Approved firm. A share
holds all the project's units or chosen ones, the project's price list in force (SOS-P7-07) and chosen
brochures (Media Assets, SOS-P4-03). A share is withdrawn, never deleted, and every share, change and
withdrawal is logged with who did it and when.

A partner reads only through `my_shared_projects` and `my_shared_project`. Both work out what the signed in
partner's firm may see at the moment of the call, from the active shares and the firm's status, so a
withdrawn share, an archived record or a firm that is Suspended stops showing at once. The partner holds no
read permission on any inventory DocType, so no other list or record method shows them anything, and nothing
here names another partner, their shares or their registrations.
"""

import frappe
from frappe import _
from frappe.utils import cint

from sellos.access.partner_firms import firm_of
from sellos.access.registry import sellos_api
from sellos.access.roles import CHANNEL_PARTNER, COMPANY_ADMIN
from sellos.inventory.pricing import price_list_in_force, price_list_view
from sellos.sellos.doctype.channel_partner_firm.channel_partner_firm import APPROVED

SHARE = "Partner Share"
FIRM = "Channel Partner Firm"
EVERY = "all"
UNIT_FIELDS = ["name", "tower", "unit_number", "configuration", "carpet_area", "floor", "parking", "status"]


def _list(value) -> list:
	value = frappe.parse_json(value) if isinstance(value, str) and value[:1] in "[{" else value
	if value in (None, ""):
		return []
	return [value] if isinstance(value, str) else list(value)


def _flag(value) -> bool:
	return str(value).lower() in ("1", "true", "yes")


# --- The Company Admin ------------------------------------------------------------------------------


def _share_view(doc) -> dict:
	people = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	firm = doc.partner_firm
	return {
		"name": doc.name,
		"project": doc.project,
		"project_name": frappe.db.get_value("Project", doc.project, "project_name"),
		"status": doc.status,
		"all_firms": cint(doc.all_firms),
		"partner_firm": firm or "",
		"firm_name": frappe.db.get_value(FIRM, firm, "firm_name") if firm else _("Every Approved firm"),
		"all_units": cint(doc.all_units),
		"units": [row.unit for row in doc.units],
		"share_price_list": cint(doc.share_price_list),
		"brochures": [row.media_asset for row in doc.brochures],
		"withdrawn_reason": doc.withdrawn_reason or "",
		"log": [
			{
				"changed_on": row.changed_on,
				"changed_by_name": people.get(row.changed_by, row.changed_by),
				"action": row.action,
				"detail": row.detail or "",
			}
			for row in doc.log
		],
	}


def _shares(project=None) -> list[dict]:
	filters = {"project": project} if project else {}
	names = frappe.get_list(SHARE, filters=filters, order_by="creation desc", pluck="name")
	return [_share_view(frappe.get_doc(SHARE, name)) for name in names]


def _state(project=None) -> dict:
	return {"shares": _shares(project)}


@sellos_api(COMPANY_ADMIN)
def partner_share_options(project=None):
	"""What a Company Admin may choose from: the projects, the Approved firms and, for one project, its units,
	its price list in force and the brochures in the library. Also its shares."""
	out = {
		"projects": frappe.get_all(
			"Project",
			filters={"archived": 0},
			fields=["name", "project_name"],
			order_by="project_name asc",
		),
		"firms": frappe.get_all(
			FIRM, filters={"status": APPROVED}, fields=["name", "firm_name"], order_by="firm_name asc"
		),
		"units": [],
		"price_list": None,
		"brochures": frappe.get_all(
			"Media Asset",
			filters={"archived": 0},
			fields=["name", "title", "media_type"],
			order_by="creation desc",
			limit=200,
		),
	}
	if project:
		if not frappe.db.exists("Project", project):
			frappe.throw(_("There is no project {0}.").format(project), frappe.DoesNotExistError)
		out["units"] = frappe.get_all(
			"Unit",
			filters={"project": project, "archived": 0},
			fields=UNIT_FIELDS,
			order_by="tower asc, unit_number asc",
		)
		forced = price_list_in_force(project)
		out["price_list"] = {"name": forced.name, "title": forced.title} if forced else None
	return {**out, **_state(project)}


@sellos_api(COMPANY_ADMIN)
def list_partner_shares(project=None):
	"""Every share, withdrawn ones included, newest first, each with its log."""
	return _state(project)


@sellos_api(COMPANY_ADMIN)
def share_project(project, firms, units=None, share_price_list=0, brochures=None):
	"""Share a project with chosen Approved firms (a list of partner codes) or with every Approved firm
	(`firms` is "all"). `units` is a list of unit names, or empty for all of the project's units."""
	if not project or not frappe.db.exists("Project", project):
		frappe.throw(_("There is no project {0}.").format(project), frappe.DoesNotExistError)
	targets = _list(firms)
	if not targets:
		frappe.throw(_("Choose the firms to share with, or every Approved firm."))
	chosen = _list(units)
	values = {
		"doctype": SHARE,
		"project": project,
		"all_units": 0 if chosen else 1,
		"units": [{"unit": u} for u in chosen],
		"share_price_list": 1 if _flag(share_price_list) else 0,
		"brochures": [{"media_asset": m} for m in _list(brochures)],
	}
	if EVERY in targets:
		frappe.get_doc({**values, "all_firms": 1}).insert()
	else:
		for firm in dict.fromkeys(targets):
			if not frappe.db.exists(FIRM, firm):
				frappe.throw(_("There is no partner firm {0}.").format(firm), frappe.DoesNotExistError)
			frappe.get_doc({**values, "all_firms": 0, "partner_firm": firm}).insert()
	return _state(project)


@sellos_api(COMPANY_ADMIN)
def update_partner_share(name, units=None, share_price_list=0, brochures=None):
	"""Change what an active share gives: its units (empty means all), the price list and the brochures."""
	doc = _share(name)
	chosen = _list(units)
	doc.all_units = 0 if chosen else 1
	doc.set("units", [{"unit": u} for u in chosen])
	doc.share_price_list = 1 if _flag(share_price_list) else 0
	doc.set("brochures", [{"media_asset": m} for m in _list(brochures)])
	doc.save()
	return _state(doc.project)


@sellos_api(COMPANY_ADMIN)
def withdraw_partner_share(name, reason=""):
	"""Withdraw a share. It stops showing to partners at once, and the withdrawal is logged."""
	doc = _share(name)
	doc.flags.withdrawing = True
	doc.flags.withdraw_reason = reason
	doc.save()
	return _state(doc.project)


def _share(name):
	if not name or not frappe.db.exists(SHARE, name):
		frappe.throw(_("There is no share {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc(SHARE, name)
	doc.check_permission("write")
	return doc


# --- The partner ------------------------------------------------------------------------------------


def _approved_firm() -> str:
	"""The signed in partner's firm, when it is Approved. Anyone else is refused."""
	firm = firm_of()
	if not firm or frappe.db.get_value(FIRM, firm, "status") != APPROVED:
		frappe.throw(_("Only a partner of an approved firm sees shared projects."), frappe.PermissionError)
	return firm


def shared_with(firm) -> dict[str, dict]:
	"""What is shared with a firm now, by project: {"units": None (all) or a set of names, "price_list": bool,
	"brochures": set of Media Asset names}. Withdrawn shares and archived projects are left out."""
	names = frappe.get_all(
		SHARE,
		filters={"status": "Active"},
		or_filters=[["partner_firm", "=", firm], ["all_firms", "=", 1]],
		order_by="creation asc",
		pluck="name",
	)
	merged: dict[str, dict] = {}
	for name in names:
		doc = frappe.get_doc(SHARE, name)
		if frappe.db.get_value("Project", doc.project, "archived"):
			continue
		entry = merged.setdefault(doc.project, {"units": set(), "price_list": False, "brochures": set()})
		if doc.all_units or entry["units"] is None:
			entry["units"] = None
		else:
			entry["units"] |= {row.unit for row in doc.units}
		entry["price_list"] = entry["price_list"] or bool(doc.share_price_list)
		entry["brochures"] |= {row.media_asset for row in doc.brochures}
	return merged


def _unit_rows(project, allowed) -> list[dict]:
	filters = {"project": project, "archived": 0}
	if allowed is not None:
		filters["name"] = ["in", sorted(allowed) or [""]]
	rows = frappe.get_all("Unit", filters=filters, fields=UNIT_FIELDS, order_by="tower asc, unit_number asc")
	for row in rows:
		if row.status == "Blocked":
			row.status = "Unavailable"
	return rows


@sellos_api(CHANNEL_PARTNER)
def my_shared_projects():
	"""The projects shared with the signed in partner's firm, with how many units are shared in each."""
	shared = shared_with(_approved_firm())
	out = []
	for project, entry in shared.items():
		row = frappe.db.get_value(
			"Project", project, ["project_name", "city", "locality", "project_status"], as_dict=True
		)
		out.append(
			{
				"name": project,
				**row,
				"units": len(_unit_rows(project, entry["units"])),
				"has_price_list": bool(entry["price_list"] and price_list_in_force(project)),
				"brochures": len(_brochures(entry)),
			}
		)
	return {"projects": sorted(out, key=lambda r: r["project_name"] or "")}


def _brochures(entry) -> list[dict]:
	if not entry["brochures"]:
		return []
	return frappe.get_all(
		"Media Asset",
		filters={"name": ["in", sorted(entry["brochures"])], "archived": 0},
		fields=["name", "title", "media_type", "file as file_url"],
		order_by="creation asc",
	)


@sellos_api(CHANNEL_PARTNER)
def my_shared_project(project):
	"""One shared project: the shared units, the price list in force when it is shared, and the brochures.
	A project that is not shared with the partner's firm is answered as if it did not exist."""
	entry = shared_with(_approved_firm()).get(project)
	if not entry:
		frappe.throw(_("There is no shared project {0}.").format(project), frappe.DoesNotExistError)
	row = frappe.db.get_value(
		"Project",
		project,
		["project_name", "rera_number", "project_status", "city", "locality", "address", "possession_date"],
		as_dict=True,
	)
	forced = price_list_in_force(project) if entry["price_list"] else None
	return {
		"project": {"name": project, **row, "possession_date": str(row.possession_date or "")},
		"units": _unit_rows(project, entry["units"]),
		"price_list": price_list_view(forced, in_force=True) if forced else None,
		"brochures": _brochures(entry),
	}
