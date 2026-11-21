"""The unit availability grid, and holds, blocks and expiry on its units (SOS-P7-06).

* An Agent (or a Company Admin) holds an Available unit for one of the leads they may see. A hold lasts
  the company setting "Unit hold hours" (default 48 hours) and is released by `expire_holds`, which the
  scheduler runs and which takes the time as an argument so a test can fix the clock.
* Two holds on one unit never both succeed. The unit's row is locked (`select ... for update`) before its
  status is read, so the second caller waits for the first, then sees Held and is refused with who holds
  it and until when.
* The holding agent or a Company Admin releases a hold. Only a Company Admin blocks or unblocks a unit,
  always with a reason.
* Booked and Sold are set only by SOS-P7-10's booking and its completion, never from here.
* A held unit shows its agent. The lead's name shows only to a user who may see that lead.
* Every change is logged on the unit with who made it and when (the status log of SOS-P4-01).
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, format_datetime, get_datetime, now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.inventory.base import AVAILABLE, BLOCKED, HELD, UNIT_STATUSES, squash

SETTINGS = "SellOS Settings"
DEFAULT_HOLD_HOURS = 48
MAX_HOLD_HOURS = 24 * 30
HOLDERS = (COMPANY_ADMIN, AGENT)
READERS = (COMPANY_ADMIN, AGENT, SALES_MANAGER)


def now():
	"""The clock. A test replaces it to fix the time."""
	return now_datetime()


def hold_hours() -> int:
	"""The company setting "Unit hold hours"."""
	hours = cint(frappe.db.get_single_value(SETTINGS, "unit_hold_hours"))
	return hours if hours > 0 else DEFAULT_HOLD_HOURS


def _full_name(user) -> str:
	return (frappe.db.get_value("User", user, "full_name") if user else "") or user or ""


def _lock(unit):
	"""The unit's status, holder and archive flag, read with the row locked until the transaction ends."""
	row = (
		frappe.db.get_value(
			"Unit",
			unit,
			["status", "held_by", "held_until", "archived"],
			as_dict=True,
			for_update=True,
		)
		if unit
		else None
	)
	if not row:
		frappe.throw(_("There is no unit {0}.").format(unit), frappe.DoesNotExistError)
	return row


def _lapsed(row, at) -> bool:
	return row.status == HELD and bool(row.held_until) and get_datetime(row.held_until) <= get_datetime(at)


def _change(unit, status, reason="", **fields):
	doc = frappe.get_doc("Unit", unit)
	doc.status = status
	doc.flags.status_reason = reason
	for key, value in fields.items():
		doc.set(key, value)
	doc.save()
	return doc


def _refuse_held(unit, row):
	frappe.throw(
		_("Unit {0} is held by {1} until {2}.").format(
			frappe.db.get_value("Unit", unit, "unit_number"),
			_full_name(row.held_by),
			format_datetime(row.held_until),
		)
	)


def _may_see_lead(lead) -> bool:
	return bool(lead) and frappe.db.exists("Lead", lead) and frappe.has_permission("Lead", "read", doc=lead)


def hold_unit_for(unit, lead, hours=None, reason="") -> dict:
	"""Hold an Available unit for a lead. The unit's row is locked first, so of two holds on one unit
	exactly one succeeds and the other is refused with who holds it and until when."""
	row = _lock(unit)
	if row.archived:
		frappe.throw(_("An archived unit can not be held."))
	at = now()
	if _lapsed(row, at):
		_change(unit, AVAILABLE, _("The hold expired."))
		row = _lock(unit)
	if row.status == HELD:
		_refuse_held(unit, row)
	if row.status != AVAILABLE:
		frappe.throw(
			_("Unit {0} is {1}, only an Available unit can be held.").format(
				frappe.db.get_value("Unit", unit, "unit_number"), row.status
			)
		)
	_change(
		unit,
		HELD,
		reason,
		held_by=frappe.session.user,
		held_for_lead=lead,
		held_until=add_to_date(at, hours=hours or hold_hours()),
	)
	return {"name": unit, "status": HELD}


def expire_holds(at=None) -> list[str]:
	"""Release every hold that has lapsed by `at` (the time now when not given). Returns the units released.
	The scheduler runs it; a test calls it with a fixed clock."""
	at = at or now()
	released = []
	for unit in frappe.get_all(
		"Unit", filters={"status": HELD, "held_until": ["<=", at]}, pluck="name", order_by="held_until asc"
	):
		row = _lock(unit)
		if _lapsed(row, at):
			_change(unit, AVAILABLE, _("The hold expired."))
			released.append(unit)
	return released


def _require_unit(unit):
	if not unit or not frappe.db.exists("Unit", unit):
		frappe.throw(_("There is no unit {0}.").format(unit), frappe.DoesNotExistError)
	frappe.get_doc("Unit", unit).check_permission("write")


# --- the whitelisted methods --------------------------------------------------------------------


@sellos_api(*HOLDERS)
def hold_unit(unit, lead, reason=""):
	"""Hold an Available unit for one of the caller's leads, for the company's Unit hold hours."""
	_require_unit(unit)
	if not _may_see_lead(lead):
		frappe.throw(_("You can hold a unit only for a lead you may see."), frappe.PermissionError)
	hold_unit_for(unit, lead, reason=squash(reason))
	return _answer(unit)


@sellos_api(*HOLDERS)
def release_hold(unit, reason=""):
	"""Release a hold. Only the agent who holds the unit, or a Company Admin, may."""
	_require_unit(unit)
	row = _lock(unit)
	if _lapsed(row, now()):
		_change(unit, AVAILABLE, _("The hold expired."))
		return _answer(unit)
	if row.status != HELD:
		frappe.throw(_("Unit {0} is not held.").format(frappe.db.get_value("Unit", unit, "unit_number")))
	if row.held_by != frappe.session.user and COMPANY_ADMIN not in frappe.get_roles():
		frappe.throw(_("Only the agent who holds the unit can release it."), frappe.PermissionError)
	_change(unit, AVAILABLE, squash(reason) or _("Hold released."))
	return _answer(unit)


@sellos_api(COMPANY_ADMIN)
def block_unit(unit, reason):
	"""Block an Available unit from sale, with a reason."""
	_require_unit(unit)
	reason = squash(reason)
	if not reason:
		frappe.throw(_("Give the reason for blocking the unit."))
	row = _lock(unit)
	if _lapsed(row, now()):
		_change(unit, AVAILABLE, _("The hold expired."))
		row = _lock(unit)
	if row.status == HELD:
		_refuse_held(unit, row)
	if row.status != AVAILABLE:
		frappe.throw(_("Only an Available unit can be blocked. This one is {0}.").format(row.status))
	_change(unit, BLOCKED, reason)
	return _answer(unit)


@sellos_api(COMPANY_ADMIN)
def unblock_unit(unit, reason):
	"""Put a Blocked unit back on sale, with a reason."""
	_require_unit(unit)
	reason = squash(reason)
	if not reason:
		frappe.throw(_("Give the reason for unblocking the unit."))
	if _lock(unit).status != BLOCKED:
		frappe.throw(_("Unit {0} is not blocked.").format(frappe.db.get_value("Unit", unit, "unit_number")))
	_change(unit, AVAILABLE, reason)
	return _answer(unit)


@sellos_api(COMPANY_ADMIN)
def get_hold_settings():
	return {"unit_hold_hours": hold_hours()}


@sellos_api(COMPANY_ADMIN)
def save_hold_settings(unit_hold_hours):
	"""Save the Unit hold hours (1 to 720). A hold already made keeps its own end time."""
	hours = cint(unit_hold_hours)
	if not 1 <= hours <= MAX_HOLD_HOURS:
		frappe.throw(_("Enter the hold hours from 1 to {0}.").format(MAX_HOLD_HOURS))
	frappe.db.set_single_value(SETTINGS, "unit_hold_hours", hours)
	return {"unit_hold_hours": hours}


# --- the grid -----------------------------------------------------------------------------------


def _answer(unit) -> dict:
	return unit_grid(frappe.db.get_value("Unit", unit, "project"))


def _blocked_reason(unit) -> str:
	rows = frappe.get_all(
		"Inventory Status Change",
		filters={"parent": unit, "parenttype": "Unit", "to_status": BLOCKED},
		fields=["reason"],
		order_by="idx desc",
		limit=1,
	)
	return (rows[0].reason or "") if rows else ""


def _cell(row, at, admin, user) -> dict:
	"""One unit on the grid. A lapsed hold shows as Available, as hold_unit treats it."""
	status = AVAILABLE if _lapsed(row, at) else row.status
	held = status == HELD
	lead = row.held_for_lead if held and _may_see_lead(row.held_for_lead) else ""
	return {
		"name": row.name,
		"tower": row.tower or "",
		"unit_number": row.unit_number,
		"floor": row.floor,
		"configuration": row.configuration or "",
		"carpet_area": row.carpet_area,
		"status": status,
		"held_by": row.held_by if held else "",
		"held_by_name": _full_name(row.held_by) if held else "",
		"held_until": str(row.held_until) if held and row.held_until else "",
		"lead": lead,
		"lead_name": frappe.db.get_value("Lead", lead, "lead_title") if lead else "",
		"blocked_reason": _blocked_reason(row.name) if status == BLOCKED else "",
		"can_hold": status == AVAILABLE,
		"can_release": held and (admin or row.held_by == user),
		"can_block": admin and status == AVAILABLE,
		"can_unblock": admin and status == BLOCKED,
	}


@sellos_api(*READERS)
def unit_grid(project, configuration="", status=""):
	"""Each tower's floors and units of a project with their status, for the grid. `configuration` and
	`status` narrow the units shown."""
	if not project or not frappe.db.exists("Project", project):
		frappe.throw(_("There is no project {0}.").format(project), frappe.DoesNotExistError)
	frappe.get_doc("Project", project).check_permission("read")
	configuration, status = squash(configuration), squash(status)
	if status and status not in UNIT_STATUSES:
		frappe.throw(_("The status must be one of {0}.").format(", ".join(UNIT_STATUSES)))
	roles, user, at = frappe.get_roles(), frappe.session.user, now()
	admin = COMPANY_ADMIN in roles
	cells = [
		_cell(row, at, admin, user)
		for row in frappe.get_all(
			"Unit",
			filters={"project": project, "archived": 0},
			fields=[
				"name",
				"tower",
				"unit_number",
				"floor",
				"configuration",
				"carpet_area",
				"status",
				"held_by",
				"held_for_lead",
				"held_until",
			],
			order_by="unit_number asc",
		)
		if not configuration or (row.configuration or "") == configuration
	]
	cells = [c for c in cells if not status or c["status"] == status]
	towers, placed = [], set()
	for name in frappe.get_all(
		"Project Tower", filters={"project": project, "archived": 0}, order_by="creation asc", pluck="name"
	):
		tower = frappe.get_doc("Project Tower", name)
		mine = [c for c in cells if c["tower"] == name]
		floors = []
		for floor in sorted(tower.floors, key=lambda f: f.floor_number, reverse=True):
			on_floor = [c for c in mine if c["floor"] == floor.floor_number]
			placed.update(c["name"] for c in on_floor)
			floors.append(
				{
					"floor_number": floor.floor_number,
					"floor_label": floor.floor_label or "",
					"units": on_floor,
				}
			)
		towers.append({"name": name, "tower_name": tower.tower_name, "floors": floors})
		placed.update(c["name"] for c in mine)
		# A unit on a floor the tower no longer lists still shows, below its floors.
		extra = [c for c in mine if c["floor"] not in {f["floor_number"] for f in floors}]
		if extra:
			towers[-1]["floors"].append({"floor_number": None, "floor_label": _("Other"), "units": extra})
	counts = {s: 0 for s in UNIT_STATUSES}
	for cell in cells:
		counts[cell["status"]] += 1
	return {
		"project": project,
		"project_name": frappe.db.get_value("Project", project, "project_name"),
		"towers": towers,
		"other_units": [c for c in cells if c["name"] not in placed],
		"counts": counts,
		"legend": list(UNIT_STATUSES),
		"configurations": [
			c for c in frappe.get_meta("Unit").get_field("configuration").options.split("\n") if c
		],
		"hold_hours": hold_hours(),
		"can_hold": any(role in roles for role in HOLDERS),
		"can_block": admin,
		"leads": _my_leads() if any(role in roles for role in HOLDERS) else [],
	}


def _my_leads() -> list[dict]:
	"""The leads the caller may see, for choosing who a unit is held for."""
	return frappe.get_list(
		"Lead",
		filters={"archived": 0},
		fields=["name", "lead_title"],
		order_by="modified desc",
		limit=200,
	)
