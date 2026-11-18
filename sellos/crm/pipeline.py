"""The buyer pipeline (SOS-P1-07): eleven stages, a stage on every lead and a log of every move.

Consent never blocks (Jayman, 10 November 2026). A lead in any consent status moves to any stage.
Moving a lead to the first contact stage (Contacted) without a live Consent Record adds a warning: it
is shown on the lead and written to the stage change log, and the move goes ahead. Nothing here
refuses a move because of consent.

A Company Admin renames, reorders and adds stages in the setup wizard (sellos.config.setup_wizard),
within MAX_STAGES and with at least one Won and one Lost stage. A stage with leads is never deleted.
"""

import frappe
from frappe import _
from frappe.model.rename_doc import rename_doc
from frappe.utils import now_datetime

from sellos.crm import consent

STAGE = "Pipeline Stage"

NEW = "New"
CONSENT_PENDING = "Consent pending"
CONTACTED = "Contacted"
QUALIFIED = "Qualified"
SITE_VISIT_BOOKED = "Site visit booked"
SITE_VISIT_DONE = "Site visit done"
NEGOTIATION = "Negotiation"
BOOKING = "Booking"
CLOSED_WON = "Closed won"
CLOSED_LOST = "Closed lost"
NURTURE = "Nurture"

DEFAULT_STAGES = [
	{"stage_name": NEW, "stage_type": "Open"},
	{"stage_name": CONSENT_PENDING, "stage_type": "Open"},
	{"stage_name": CONTACTED, "stage_type": "Open"},
	{"stage_name": QUALIFIED, "stage_type": "Open"},
	{"stage_name": SITE_VISIT_BOOKED, "stage_type": "Open"},
	{"stage_name": SITE_VISIT_DONE, "stage_type": "Open"},
	{"stage_name": NEGOTIATION, "stage_type": "Open"},
	{"stage_name": BOOKING, "stage_type": "Won"},
	{"stage_name": CLOSED_WON, "stage_type": "Won"},
	{"stage_name": CLOSED_LOST, "stage_type": "Lost"},
	{"stage_name": NURTURE, "stage_type": "Open"},
]

# The stages of the seven stage list SOS-P1-03 seeded, and where their leads go. New, Contacted, Site
# visit done and Negotiation keep their names.
OLD_TO_NEW = {
	"Site visit scheduled": SITE_VISIT_BOOKED,
	"Booked": BOOKING,
	"Lost": CLOSED_LOST,
}


def _make_stage(name, stage_type, position):
	frappe.get_doc(
		{
			"doctype": STAGE,
			"stage_name": name,
			"stage_type": stage_type,
			"position": position,
			"is_contact_stage": 1 if name == CONTACTED else 0,
		}
	).insert(ignore_permissions=True)


def ensure_default_stages() -> list[str]:
	"""Make the eleven stages on a site that has none. A site that has stages keeps them: a Company
	Admin may have renamed or removed some, and a stage is never made again behind their back. The
	patch p1_07_buyer_pipeline carries an older list over. Safe to run again."""
	if frappe.db.count(STAGE):
		return []
	for position, stage in enumerate(DEFAULT_STAGES, start=1):
		_make_stage(stage["stage_name"], stage["stage_type"], position)
	return [s["stage_name"] for s in DEFAULT_STAGES]


def first_stage() -> str:
	"""The stage a new lead starts on: the first one in the list."""
	ensure_default_stages()
	return frappe.get_all(STAGE, pluck="name", order_by="position asc, stage_name asc", limit=1)[0]


def list_stages() -> list[dict]:
	"""The stages in order, with how many leads each holds."""
	rows = frappe.get_all(
		STAGE,
		fields=["name", "stage_type", "position", "is_contact_stage"],
		order_by="position asc, stage_name asc",
	)
	counts = dict(
		frappe.db.sql("select stage, count(*) from `tabLead` where stage is not null group by stage")
	)
	return [
		{
			"name": row.name,
			"stage_type": row.stage_type,
			"position": row.position,
			"is_contact_stage": int(row.is_contact_stage or 0),
			"leads": int(counts.get(row.name, 0)),
		}
		for row in rows
	]


def lead_count(stage) -> int:
	"""Every lead on the stage, archived ones too: an archived lead is still a record."""
	return frappe.db.count("Lead", {"stage": stage})


def ensure_deletable(stage) -> None:
	"""Refuse to delete a stage that has leads, and say how many."""
	count = lead_count(stage)
	if count:
		frappe.throw(
			_(
				"The stage {0} has {1} lead(s) and cannot be deleted. Move them to another stage first."
			).format(stage, count),
			frappe.ValidationError,
		)


def contact_warning(lead, stage, moved=True) -> dict | None:
	"""The warning for a lead that is on, or is moving to, the first contact stage with no live Consent
	Record. None for any other stage and for a Consented lead. It is a warning only: it never stops
	the move, a call, an SMS or a WhatsApp message."""
	if not frappe.db.get_value(STAGE, stage, "is_contact_stage"):
		return None
	status = consent.compute_status(lead)
	if status == consent.CONSENTED:
		return None
	level, message = consent.WARNINGS[status]
	if consent.has_live_record(lead):
		lead_part = _("Moved to {0}.") if moved else _("This lead is on {0}.")
	else:
		lead_part = (
			_("Moved to {0} without a live Consent Record.")
			if moved
			else _("This lead is on {0} without a live Consent Record.")
		)
	return {"level": level, "status": status, "message": f"{lead_part.format(stage)} {message}"}


def check_lost_reason(stage, lost_reason) -> str | None:
	"""A move to a Lost stage asks for a reason from the Lost Reason list (SOS-P1-21), and a new choice
	must be an enabled one. Returns the reason to record, or None for a stage that is not a Lost stage.
	This is the only thing besides a missing stage that refuses a move, and it never looks at consent."""
	if frappe.db.get_value(STAGE, stage, "stage_type") != "Lost":
		return None
	if not lost_reason:
		frappe.throw(_("Choose a lost reason to move the lead to {0}.").format(stage), frappe.MandatoryError)
	if not frappe.db.get_value("Lost Reason", lost_reason, "enabled"):
		frappe.throw(_("{0} is not an available lost reason. Choose another.").format(lost_reason))
	return lost_reason


def move_lead(lead, stage, lost_reason=None) -> dict:
	"""Move a lead to any stage, whatever its consent status, and log the move.

	The caller has checked the user may write the lead. A stage that does not exist is refused, and so is
	a move to a Lost stage with no lost reason (SOS-P1-21). Returns {"lead", "previous", "stage", "moved",
	"warning"}."""
	doc = frappe.get_doc("Lead", lead)
	if not frappe.db.exists(STAGE, stage):
		frappe.throw(_("{0} is not a stage of the pipeline.").format(stage))
	stage = frappe.db.get_value(STAGE, stage, "name")
	previous = doc.stage
	if previous == stage:
		return {"lead": lead, "previous": previous, "stage": stage, "moved": False, "warning": None}
	reason = check_lost_reason(stage, lost_reason)
	warning = contact_warning(lead, stage, moved=True)
	doc.stage = stage
	doc.lost_reason = reason  # cleared when the lead leaves a Lost stage
	doc.append(
		"stage_log",
		{
			"changed_on": now_datetime(),
			"changed_by": frappe.session.user,
			"from_stage": previous or "",
			"to_stage": stage,
			"lost_reason": reason or "",
			"warning": warning["message"] if warning else "",
		},
	)
	doc.flags.ignore_permissions = True  # the caller checked write
	doc.save()
	return {"lead": lead, "previous": previous, "stage": stage, "moved": True, "warning": warning}


def stage_view(doc) -> dict:
	"""What the lead screen shows: the stage, its warning and the log, newest first."""
	log = [
		{
			"changed_on": row.changed_on,
			"changed_by": row.changed_by,
			"from_stage": row.from_stage,
			"to_stage": row.to_stage,
			"lost_reason": row.lost_reason or "",
			"warning": row.warning or "",
		}
		for row in sorted(doc.stage_log, key=lambda r: (str(r.changed_on), r.idx), reverse=True)
	]
	return {
		"stage": doc.stage,
		"lost_reason": doc.lost_reason or "",
		"warning": contact_warning(doc.name, doc.stage, moved=False) if doc.stage else None,
		"log": log,
		"stages": list_stages(),
	}


# --- The patch: carry an older stage list and its leads over -----------------------------------


def _set_positions():
	"""The eleven standard stages in order first, any stage a company added after them."""
	standard = [s["stage_name"].lower() for s in DEFAULT_STAGES]
	rows = frappe.get_all(STAGE, fields=["name", "position"], order_by="position asc, name asc")
	ordered = sorted(
		rows,
		key=lambda r: (0, standard.index(r.name.lower())) if r.name.lower() in standard else (1, r.position),
	)
	for position, row in enumerate(ordered, start=1):
		if row.position != position:
			frappe.db.set_value(STAGE, row.name, "position", position, update_modified=False)


def carry_over_stages() -> dict:
	"""Bring a site's stages and leads to the eleven stage pipeline (SOS-P1-07). Running it again
	changes nothing.

	* A site with no stages gets the eleven.
	* Site visit scheduled becomes Site visit booked, Booked becomes Booking and Lost becomes Closed
	  lost, with their leads. New, Contacted, Site visit done and Negotiation keep theirs.
	* The stages the old list lacked are added, and the standard ones are put in order.
	* A lead with no stage is put on the first one.
	Returns {"seeded", "renamed", "added", "leads_moved", "leads_placed"}.
	"""
	result = {"seeded": ensure_default_stages(), "renamed": [], "added": [], "leads_moved": 0}
	names = {name.lower(): name for name in frappe.get_all(STAGE, pluck="name")}
	for old, new in OLD_TO_NEW.items():
		leads = frappe.db.count("Lead", {"stage": old})
		old_name = names.get(old.lower())
		if old_name and new.lower() not in names:
			rename_doc(
				STAGE,
				old_name,
				new,
				force=True,
				ignore_permissions=True,
				rebuild_search=False,
				show_alert=False,
			)
			names.pop(old.lower())
			names[new.lower()] = new
			result["renamed"].append(f"{old} -> {new}")
		# Leads that still name the old stage: a stage that existed beside the new one, or none at all.
		if leads:
			frappe.db.sql("update `tabLead` set stage = %s where stage = %s", (new, old))
			result["leads_moved"] += leads
		if old.lower() in names and new.lower() in names and old.lower() != new.lower():
			frappe.delete_doc(STAGE, names.pop(old.lower()), ignore_permissions=True)
	for stage in DEFAULT_STAGES:
		if stage["stage_name"].lower() not in names:
			_make_stage(stage["stage_name"], stage["stage_type"], len(names) + 1)
			names[stage["stage_name"].lower()] = stage["stage_name"]
			result["added"].append(stage["stage_name"])
	if CONTACTED.lower() in names:
		frappe.db.set_value(STAGE, names[CONTACTED.lower()], "is_contact_stage", 1, update_modified=False)
	_set_positions()
	first = first_stage()
	unplaced = frappe.db.sql("select count(*) from `tabLead` where stage is null or stage = ''")[0][0]
	if unplaced:
		frappe.db.sql("update `tabLead` set stage = %s where stage is null or stage = ''", (first,))
	result["leads_placed"] = unplaced
	return result
