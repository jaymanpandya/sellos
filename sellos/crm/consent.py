"""Consent Records and each lead's consent status (P1.08).

Consent never blocks (Jayman, 10 November 2026). Everything here records a status and describes
the warning to show. Nothing here, and nothing that reads it, may refuse a call, an SMS or a
WhatsApp message. Enforcement, when it is built (P2.04), lives in one function behind the company
setting "Consent enforcement", which is Off by default.

Status of a lead, first match wins:
* Opted out: an explicit stop request was recorded, with its time and source.
* Registered DND: a do not call result is known for the number.
* Consented: a live Consent Record exists (not yet expired).
* Unknown: anything else, including a lead whose only records have expired.

A new Consent Record never clears Opted out or Registered DND, because those say the lead asked
not to be contacted, or the number is on the register, and a basis is not the same thing.
"""

import re

import frappe
from frappe import _
from frappe.utils import add_days, add_months, get_datetime, now_datetime

CONSENTED = "Consented"
UNKNOWN = "Unknown"
OPTED_OUT = "Opted out"
REGISTERED_DND = "Registered DND"
STATUSES = (UNKNOWN, CONSENTED, OPTED_OUT, REGISTERED_DND)

BASES = ("Consent", "Inquiry", "Application")
INQUIRY_DAYS = 7
APPLICATION_MONTHS = 3
STOP_SOURCES = ("Phone call", "WhatsApp", "SMS", "Email", "In person", "Website", "Other")

# red for an explicit stop, amber for the two cases where permission is not established, none otherwise.
WARNINGS = {
	OPTED_OUT: ("red", "Opted out. This lead asked to stop being contacted."),
	REGISTERED_DND: ("amber", "Registered on the do not call list."),
	UNKNOWN: ("amber", "Consent unknown. There is no live consent record for this lead."),
	CONSENTED: (None, ""),
}

_EVIDENCE = re.compile(r"^(https?://\S+|/(?:private/)?files/\S+)$", re.IGNORECASE)


def expiry_for(basis, recorded_on):
	"""When a record of this basis lapses. Consent has no expiry."""
	recorded_on = get_datetime(recorded_on)
	if basis == "Inquiry":
		return add_days(recorded_on, INQUIRY_DAYS)
	if basis == "Application":
		return add_months(recorded_on, APPLICATION_MONTHS)
	return None


def prepare_record(doc):
	"""Validate a Consent Record and set its expiry from its basis."""
	doc.evidence_link = (doc.evidence_link or "").strip()
	if not doc.evidence_link:
		frappe.throw(_("A consent record needs an evidence link."))
	if not _EVIDENCE.match(doc.evidence_link):
		frappe.throw(_("The evidence link must be a web address or a file kept in the company's files."))
	if doc.basis not in BASES:
		frappe.throw(_("The basis must be Consent, Inquiry or Application."))
	if not doc.is_new():
		for field in ("lead", "basis", "recorded_on", "evidence_link"):
			if doc.has_value_changed(field):
				frappe.throw(_("A consent record is never edited. Record a new one to renew it."))
	doc.recorded_on = doc.recorded_on or now_datetime()
	doc.expires_on = expiry_for(doc.basis, doc.recorded_on)
	if doc.is_new():
		_link_renewal(doc)


def _latest_same_basis(lead, basis, before=None):
	filters = {"lead": lead, "basis": basis, "archived": 0}
	if before:
		filters["recorded_on"] = ["<=", before]
	rows = frappe.get_all(
		"Consent Record",
		filters=filters,
		fields=["name", "renewal_count"],
		order_by="recorded_on desc, creation desc",
		limit=1,
	)
	return rows[0] if rows else None


def _link_renewal(doc):
	"""A record for a lead that already has one of the same basis renews it."""
	previous = _latest_same_basis(doc.lead, doc.basis)
	if previous:
		doc.renews = previous.name
		doc.renewal_count = (previous.renewal_count or 0) + 1


def log_renewal(doc):
	"""Renewals are logged: a note on the lead says which record was renewed and for how long."""
	if not doc.renews:
		return
	until = doc.expires_on or _("no expiry")
	frappe.get_doc("Lead", doc.lead).add_comment(
		"Info",
		_("Consent record {0} renews {1} ({2}). Renewal number {3}, valid until {4}.").format(
			doc.name, doc.renews, doc.basis, doc.renewal_count, until
		),
	)


def has_live_record(lead, on=None) -> bool:
	on = get_datetime(on or now_datetime())
	return bool(
		frappe.db.sql(
			"""select 1 from `tabConsent Record`
			where lead = %s and archived = 0 and recorded_on <= %s
			and (expires_on is null or expires_on > %s) limit 1""",
			(lead, on, on),
		)
	)


def compute_status(lead, on=None) -> str:
	"""The lead's consent status as of `on` (now by default), from the records. Always current."""
	row = frappe.db.get_value("Lead", lead, ["opted_out_on", "dnd_registered"], as_dict=True)
	if not row:
		frappe.throw(_("Lead {0} was not found.").format(lead), frappe.DoesNotExistError)
	if row.opted_out_on:
		return OPTED_OUT
	if row.dnd_registered:
		return REGISTERED_DND
	return CONSENTED if has_live_record(lead, on) else UNKNOWN


def sync_lead_status(lead, on=None) -> str:
	"""Store the computed status on the lead when it changed. The change is tracked on the lead."""
	status = compute_status(lead, on)
	if frappe.db.get_value("Lead", lead, "consent_status") != status:
		doc = frappe.get_doc("Lead", lead)
		doc.consent_status = status
		doc.flags.ignore_permissions = True  # the status is system maintained, never typed in
		doc.save()
	return status


def expire_due_records(on=None) -> list[str]:
	"""Scheduled hourly: a lead whose only live record has expired goes back to Unknown."""
	changed = []
	for lead in frappe.get_all("Lead", filters={"consent_status": CONSENTED}, pluck="name"):
		if sync_lead_status(lead, on) != CONSENTED:
			changed.append(lead)
	return changed


def record_opt_out(lead, source, on=None):
	"""An explicit stop request. Stored with its time and source. The first one is kept."""
	if source not in STOP_SOURCES:
		frappe.throw(_("Choose how the lead asked to stop: {0}.").format(", ".join(STOP_SOURCES)))
	doc = frappe.get_doc("Lead", lead)
	if not doc.opted_out_on:
		doc.opted_out_on = get_datetime(on or now_datetime())
		doc.opted_out_source = source
		doc.flags.ignore_permissions = True
		doc.save()
	return sync_lead_status(lead)


def record_dnd_result(lead, registered, on=None):
	"""A do not call result for the lead's number: registered or not registered."""
	doc = frappe.get_doc("Lead", lead)
	doc.dnd_registered = 1 if registered else 0
	doc.dnd_checked_on = get_datetime(on or now_datetime())
	doc.flags.ignore_permissions = True
	doc.save()
	return sync_lead_status(lead)


def consent_view(lead, on=None) -> dict:
	"""What the screens show: the status, its warning, and the records, newest first."""
	status = compute_status(lead, on)
	level, message = WARNINGS[status]
	row = frappe.db.get_value(
		"Lead", lead, ["opted_out_on", "opted_out_source", "dnd_checked_on"], as_dict=True
	)
	if status == OPTED_OUT:
		message = _("Opted out on {0} through {1}. This lead asked to stop being contacted.").format(
			str(row.opted_out_on)[:16], row.opted_out_source or _("an unrecorded source")
		)
	now = get_datetime(on or now_datetime())
	records = frappe.get_list(
		"Consent Record",
		filters={"lead": lead, "archived": 0},
		fields=["name", "basis", "recorded_on", "evidence_link", "expires_on", "renews", "renewal_count"],
		order_by="recorded_on desc, creation desc",
		limit_page_length=50,
	)
	for record in records:
		record["live"] = bool(record.expires_on is None or get_datetime(record.expires_on) > now)
	return {
		"status": status,
		"warning": level,
		"message": message,
		"opted_out_on": row.opted_out_on,
		"opted_out_source": row.opted_out_source,
		"dnd_checked_on": row.dnd_checked_on,
		"records": records,
	}
