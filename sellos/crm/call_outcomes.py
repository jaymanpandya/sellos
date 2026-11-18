"""Call outcomes, logging a call by hand and the lost reasons (SOS-P1-21).

A Company Admin keeps two lists: the Call Outcome list (each outcome with an optional suggested stage and
whether it needs a follow up) and the Lost Reason list. SOS-P2-07's outcome form and SOS-P2-05's Call Log
use the Call Outcome list and define none of their own.

Logging a call writes a Call activity on the lead with the outcome, notes and duration, and creates the
follow up (a Lead Task, SOS-P1-22) when the outcome needs one. The outcome's suggested stage is offered
to the agent and never applied for them. Consent never blocks: nothing here reads a lead's consent status,
and a lead in any status can be logged and moved to any stage.
"""

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

from sellos.crm import pipeline

OUTCOME = "Call Outcome"
REASON = "Lost Reason"

INTERESTED = "Interested"
CALL_BACK_LATER = "Call back later"
NOT_REACHABLE = "Not reachable"
BUSY = "Busy"
WRONG_NUMBER = "Wrong number"
NOT_INTERESTED = "Not interested"
SITE_VISIT_BOOKED = "Site visit booked"

# name, needs a follow up, suggested stage. A stage a company renamed or removed is simply not suggested.
DEFAULT_OUTCOMES = (
	(INTERESTED, 1, pipeline.QUALIFIED),
	(CALL_BACK_LATER, 1, pipeline.CONTACTED),
	(NOT_REACHABLE, 1, None),
	(BUSY, 1, None),
	(WRONG_NUMBER, 0, pipeline.CLOSED_LOST),
	(NOT_INTERESTED, 0, pipeline.CLOSED_LOST),
	(SITE_VISIT_BOOKED, 0, pipeline.SITE_VISIT_BOOKED),
)
DEFAULT_OUTCOME_NAMES = tuple(row[0] for row in DEFAULT_OUTCOMES)

DEFAULT_LOST_REASONS = (
	"Budget too low",
	"Bought elsewhere",
	"No longer looking",
	"Location does not suit",
	"Not reachable",
	"Wrong number",
	"Other",
)


def ensure_default_outcomes() -> list[str]:
	"""Create any of the seven outcomes that is missing. One a Company Admin changed or disabled is left
	as it is. Safe to run again. Runs after the stages are made, so a suggested stage can be linked."""
	made = []
	for name, needs_follow_up, stage in DEFAULT_OUTCOMES:
		if frappe.db.exists(OUTCOME, name):
			continue
		frappe.get_doc(
			{
				"doctype": OUTCOME,
				"outcome_name": name,
				"enabled": 1,
				"needs_follow_up": needs_follow_up,
				"suggested_stage": stage if stage and frappe.db.exists(pipeline.STAGE, stage) else None,
			}
		).insert(ignore_permissions=True)
		made.append(name)
	return made


def ensure_default_lost_reasons() -> list[str]:
	"""Create any standard lost reason that is missing. A disabled one stays disabled. Safe to run again."""
	made = []
	for name in DEFAULT_LOST_REASONS:
		if not frappe.db.exists(REASON, name):
			frappe.get_doc({"doctype": REASON, "reason_name": name, "enabled": 1}).insert(
				ignore_permissions=True
			)
			made.append(name)
	return made


def ensure_defaults() -> dict:
	"""The after migrate and company setup hook: the outcomes and the lost reasons."""
	return {"outcomes": ensure_default_outcomes(), "lost_reasons": ensure_default_lost_reasons()}


def ensure_outcome_deletable(name) -> None:
	"""Refuse to delete an outcome a call used, or one of the seven the product names."""
	count = frappe.db.count("Lead Activity", {"outcome": name})
	if count:
		frappe.throw(
			_("{0} is used by {1} call(s) and cannot be deleted. Disable it instead.").format(name, count),
			frappe.ValidationError,
		)
	if name in DEFAULT_OUTCOME_NAMES:
		frappe.throw(_("{0} is a standard outcome and cannot be deleted. Disable it instead.").format(name))


def ensure_reason_deletable(name) -> None:
	"""Refuse to delete a lost reason a lead used, or one of the standard ones."""
	count = frappe.db.count("Lead", {"lost_reason": name})
	if count:
		frappe.throw(
			_("{0} is used by {1} lead(s) and cannot be deleted. Disable it instead.").format(name, count),
			frappe.ValidationError,
		)
	if name in DEFAULT_LOST_REASONS:
		frappe.throw(_("{0} is a standard reason and cannot be deleted. Disable it instead.").format(name))


def list_outcomes(include_disabled=False) -> list[dict]:
	filters = {} if include_disabled else {"enabled": 1}
	rows = frappe.get_all(
		OUTCOME,
		filters=filters,
		fields=["name", "enabled", "needs_follow_up", "suggested_stage"],
		order_by="creation asc, name asc",
	)
	return [
		{
			"name": row.name,
			"enabled": cint(row.enabled),
			"needs_follow_up": cint(row.needs_follow_up),
			"suggested_stage": row.suggested_stage or "",
		}
		for row in rows
	]


def list_lost_reasons(include_disabled=False) -> list[dict]:
	filters = {} if include_disabled else {"enabled": 1}
	rows = frappe.get_all(
		REASON, filters=filters, fields=["name", "enabled"], order_by="creation asc, name asc"
	)
	return [{"name": row.name, "enabled": cint(row.enabled)} for row in rows]


def _outcome(name) -> dict:
	if not name or not frappe.db.exists(OUTCOME, name):
		frappe.throw(_("Choose an outcome from the list."), frappe.MandatoryError)
	row = frappe.db.get_value(
		OUTCOME, name, ["name", "enabled", "needs_follow_up", "suggested_stage"], as_dict=True
	)
	if not row.enabled:
		frappe.throw(_("The outcome {0} is disabled. Choose another.").format(name))
	return row


def log_call(
	lead,
	outcome,
	notes=None,
	duration_seconds=None,
	follow_up_at=None,
	stage=None,
	lost_reason=None,
	called_at=None,
) -> dict:
	"""Record a call on a lead as a Call activity, and the follow up its outcome needs.

	The caller has checked the user may write the lead. Everything is checked before anything is written,
	so a refused call leaves nothing behind:
	* the outcome must be an enabled one from the list;
	* an outcome that needs a follow up needs `follow_up_at`, a date and time, and creates a Lead Task;
	* `stage` is the agent's own choice, any stage of the pipeline. The outcome's suggested stage is only
	  returned as `suggested_stage` for the screen to offer, and a Lost stage needs `lost_reason`.
	Returns {"activity", "follow_up", "suggested_stage", "stage", "moved", "warning"}."""
	row = _outcome(outcome)
	duration = cint(duration_seconds)
	if duration < 0:
		frappe.throw(_("The duration of a call cannot be negative."))
	follow_up = get_datetime(follow_up_at) if follow_up_at else None
	if row.needs_follow_up and not follow_up:
		frappe.throw(
			_("The outcome {0} needs a follow up. Enter its date and time.").format(row.name),
			frappe.MandatoryError,
		)
	if stage:
		if not frappe.db.exists(pipeline.STAGE, stage):
			frappe.throw(_("{0} is not a stage of the pipeline.").format(stage))
		reason = pipeline.check_lost_reason(stage, lost_reason)
	lead_doc = frappe.get_doc("Lead", lead)
	previous = lead_doc.stage

	activity = frappe.get_doc(
		{
			"doctype": "Lead Activity",
			"lead": lead,
			"activity_type": "Call",
			"activity_date": get_datetime(called_at) if called_at else now_datetime(),
			"outcome": row.name,
			"duration_seconds": duration,
			"notes": notes,
		}
	)
	activity.check_permission("create")
	activity.flags.ignore_permissions = True
	activity.insert()

	task_name = None
	if follow_up:
		task = frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": lead,
				"title": _("Follow up: {0}").format(row.name),
				"due_at": follow_up,
				"status": "Open",
				"assigned_to": lead_doc.assigned_to or frappe.session.user,
				"notes": notes,
			}
		)
		task.check_permission("create")
		task.flags.ignore_permissions = True
		task.insert()
		task_name = task.name

	result = {"moved": False, "warning": None, "stage": previous}
	if stage:
		result = pipeline.move_lead(lead, stage, lost_reason=reason)
	suggested = (
		row.suggested_stage if row.suggested_stage and row.suggested_stage != result["stage"] else None
	)
	return {
		"activity": activity.name,
		"follow_up": task_name,
		"suggested_stage": suggested,
		"stage": result["stage"],
		"moved": result["moved"],
		"warning": result["warning"],
	}
