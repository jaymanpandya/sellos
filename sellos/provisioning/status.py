"""The statuses of a Tenant and of a Provisioning Job, and the order they may change in (P1.01).

A new record is Requested. Provisioning starts it, and ends either Active or Failed. A Failed record
may be tried again, which sends it back to Provisioning (the worker in P1.02 retries this way). An
Active record never changes status again. Nothing may skip a step, and nothing goes back to Requested.
"""

import frappe
from frappe import _

REQUESTED = "Requested"
PROVISIONING = "Provisioning"
ACTIVE = "Active"
FAILED = "Failed"

STATUSES = (REQUESTED, PROVISIONING, ACTIVE, FAILED)

# status -> the statuses it may change to
TRANSITIONS = {
	REQUESTED: (PROVISIONING,),
	PROVISIONING: (ACTIVE, FAILED),
	ACTIVE: (),
	FAILED: (PROVISIONING,),
}


def can_change(old, new) -> bool:
	"""True when a record in status `old` may move to `new`. Staying in the same status is allowed."""
	return old == new or new in TRANSITIONS.get(old, ())


def check_new(doc):
	"""A record is made Requested. A caller can not start it further along."""
	if not doc.status:
		doc.status = REQUESTED
	if doc.status != REQUESTED:
		frappe.throw(_("A new record starts as Requested."))


def check_change(doc):
	"""Refuse a change of status that is not in the allowed order."""
	before = doc.get_doc_before_save()
	old = before.status if before else REQUESTED
	if doc.status not in STATUSES:
		frappe.throw(_("{0} is not a status.").format(doc.status))
	if not can_change(old, doc.status):
		allowed = ", ".join(TRANSITIONS.get(old, ())) or _("nothing")
		frappe.throw(_("A record that is {0} can only move to: {1}.").format(old, allowed))
