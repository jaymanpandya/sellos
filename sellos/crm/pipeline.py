"""The buyer (SOS-P1-07) and seller (SOS-P4-04) pipelines: a stage on every lead and a log of every move.

A stage belongs to the Buyer or the Seller pipeline, and a lead to one of them. A seller is a Lead on the
Seller pipeline, linked to a Client (Jayman, SOS-SETUP-34). The limits (MAX_STAGES, one Won and one Lost
stage, no delete with leads) apply to each pipeline on its own. The rule that a seller cannot reach Listed
without a signed mandate is SOS-P4-05's: it needs Mandate, and hooks in through check_stage_rules.

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

BUYER = "Buyer"
SELLER = "Seller"
PIPELINES = (BUYER, SELLER)

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

SELLER_NEW_ENQUIRY = "New owner enquiry"
SELLER_QUALIFIED = "Qualified"
VALUATION_SHARED = "Valuation shared"
MANDATE_PROPOSED = "Mandate proposed"
MANDATE_SIGNED = "Mandate signed"
LISTED = "Listed"
OFFERS_RECEIVED = "Offers received"
SOLD = "Sold"
SELLER_CLOSED_LOST = "Closed lost"
SELLER_NURTURE = "Nurture"

SELLER_STAGES = [
	{"stage_name": SELLER_NEW_ENQUIRY, "stage_type": "Open"},
	{"stage_name": SELLER_QUALIFIED, "stage_type": "Open"},
	{"stage_name": VALUATION_SHARED, "stage_type": "Open"},
	{"stage_name": MANDATE_PROPOSED, "stage_type": "Open"},
	{"stage_name": MANDATE_SIGNED, "stage_type": "Open"},
	{"stage_name": LISTED, "stage_type": "Open"},
	{"stage_name": OFFERS_RECEIVED, "stage_type": "Open"},
	{"stage_name": SOLD, "stage_type": "Won"},
	{"stage_name": SELLER_CLOSED_LOST, "stage_type": "Lost"},
	{"stage_name": SELLER_NURTURE, "stage_type": "Open"},
]

# The stages of the seven stage list SOS-P1-03 seeded, and where their leads go. New, Contacted, Site
# visit done and Negotiation keep their names.
OLD_TO_NEW = {
	"Site visit scheduled": SITE_VISIT_BOOKED,
	"Booked": BOOKING,
	"Lost": CLOSED_LOST,
}


def stage_doc_name(pipeline, stage_name) -> str:
	"""The record name of a stage: the stage's own name on the buyer pipeline, "Seller <name>" on the seller
	pipeline (SOS-P4-04), so a name may be used on both."""
	return f"Seller {stage_name}" if pipeline == SELLER else stage_name


def stages_of(pipeline) -> list[str]:
	"""The record names of the stages of one pipeline, in order."""
	return frappe.get_all(
		STAGE, filters={"pipeline": pipeline}, pluck="name", order_by="position asc, stage_name asc"
	)


def pipeline_of_stage(stage) -> str | None:
	return frappe.db.get_value(STAGE, stage, "pipeline") if stage else None


def _make_stage(name, stage_type, position, pipeline=BUYER):
	frappe.get_doc(
		{
			"doctype": STAGE,
			"pipeline": pipeline,
			"stage_name": name,
			"stage_type": stage_type,
			"position": position,
			"is_contact_stage": 1 if name == CONTACTED else 0,
		}
	).insert(ignore_permissions=True)


def ensure_default_stages(pipeline=BUYER) -> list[str]:
	"""Make the stages of a pipeline (eleven buyer stages, ten seller stages) on a site whose pipeline has
	none. A site that has stages keeps them: a Company
	Admin may have renamed or removed some, and a stage is never made again behind their back. The
	patch p1_07_buyer_pipeline carries an older list over. Safe to run again."""
	if pipeline not in PIPELINES:
		frappe.throw(_("The pipeline is Buyer or Seller."))
	if frappe.db.count(STAGE, {"pipeline": pipeline}):
		return []
	defaults = SELLER_STAGES if pipeline == SELLER else DEFAULT_STAGES
	for position, stage in enumerate(defaults, start=1):
		_make_stage(stage["stage_name"], stage["stage_type"], position, pipeline)
	return [s["stage_name"] for s in defaults]


def first_stage(pipeline=BUYER) -> str:
	"""The stage a new lead of the pipeline starts on: the first one in its list."""
	ensure_default_stages(pipeline)
	return stages_of(pipeline)[0]


def list_stages(pipeline=BUYER) -> list[dict]:
	"""The stages of one pipeline in order, with how many leads each holds. `label` is the stage's own name."""
	if pipeline not in PIPELINES:
		frappe.throw(_("The pipeline is Buyer or Seller."))
	rows = frappe.get_all(
		STAGE,
		filters={"pipeline": pipeline},
		fields=["name", "stage_name", "stage_type", "position", "is_contact_stage"],
		order_by="position asc, stage_name asc",
	)
	counts = dict(
		frappe.db.sql("select stage, count(*) from `tabLead` where stage is not null group by stage")
	)
	return [
		{
			"name": row.name,
			"label": row.stage_name,
			"pipeline": pipeline,
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


def check_stage_pipeline(doc, stage) -> None:
	"""A lead moves only along its own pipeline: a seller never lands on a buyer stage, nor a buyer on a
	seller stage (SOS-P4-04)."""
	lead_pipeline = doc.get("pipeline") or BUYER
	if pipeline_of_stage(stage) != lead_pipeline:
		frappe.throw(_("{0} is not a stage of the {1} pipeline.").format(stage, lead_pipeline))


def check_stage_rules(doc, stage, previous) -> None:
	"""The rules of a move into `stage`, besides the Lost reason. Seller stages have none yet. SOS-P4-05
	adds here that a seller cannot reach Listed without a signed Mandate."""


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
	check_stage_pipeline(doc, stage)
	previous = doc.stage
	if previous == stage:
		return {"lead": lead, "previous": previous, "stage": stage, "moved": False, "warning": None}
	check_stage_rules(doc, stage, previous)
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
		"pipeline": doc.get("pipeline") or BUYER,
		"stages": list_stages(doc.get("pipeline") or BUYER),
	}


# --- The patch: carry an older stage list and its leads over -----------------------------------


def _set_positions():
	"""The eleven standard stages in order first, any stage a company added after them."""
	standard = [s["stage_name"].lower() for s in DEFAULT_STAGES]
	rows = frappe.get_all(
		STAGE, filters={"pipeline": BUYER}, fields=["name", "position"], order_by="position asc, name asc"
	)
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
	names = {name.lower(): name for name in stages_of(BUYER)}
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
			frappe.db.set_value(STAGE, new, "stage_name", new, update_modified=False)
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
