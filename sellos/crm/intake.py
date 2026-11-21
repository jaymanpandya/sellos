"""The one lead intake function (SOS-P2-08).

A person reaches the company on their own: a missed call to the 022 number, the enquiry page, a website
form (SOS-P1-09) or a message (SOS-P5-06). Every route calls `take` and builds no second path, so a
number is matched, a lead is made or merged and consent is recorded the same way everywhere.

* The person is matched with `sellos.crm.duplicates.find_matches` (phone, then email). A known person
  keeps their lead and its stage: nothing here moves a lead along the pipeline. An unknown person gets a
  client and a lead on the first stage (New).
* A contact is an inquiry Consent Record (7 days), with the raw event or submission saved as a private
  file as its evidence, and a Lead Activity. The lead becomes Consented through the one status function.
* An explicit stop request is recorded as Opted out, with its source. The red warning shows on the lead,
  the caller queue and the call log. It does not block a later call, SMS or WhatsApp message (Jayman,
  10 November 2026), and it records no inquiry: a person who says stop has not asked to be called.

The caller decides who may call it. A public method reaches it only through `sellos.access.public_intake`
and the provider webhook only after its signature check, so this function does no permission check and
writes with `ignore_permissions`.
"""

import json

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.file_manager import save_file

from sellos.crm import consent
from sellos.crm.duplicates import find_matches, normalise_phone
from sellos.crm.lead_sources import ensure_default_sources

CALL, NOTE = "Call", "Note"


def _live_lead(client):
	rows = frappe.get_all(
		"Lead", filters={"client": client, "archived": 0}, pluck="name", order_by="creation desc", limit=1
	)
	return rows[0] if rows else None


def _find_lead(phone, email):
	"""The newest live lead of the person who owns this phone or email, or (client, None)."""
	for match in find_matches(phone=phone, email=email):
		if match["archived"]:
			continue
		lead = _live_lead(match["name"])
		if lead:
			return match["name"], lead
	for match in find_matches(phone=phone, email=email):
		if not match["archived"]:
			return match["name"], None
	return None, None


def _new_client(name, phone, email):
	client = frappe.get_doc(
		{
			"doctype": "Client",
			"client_name": name,
			"client_type": "Buyer",
			"phone": phone,
			"email": email or None,
		}
	)
	client.flags.ignore_permissions = True  # the intake route is the check; phone is a level 1 field
	return client.insert().name


def _new_lead(client, source, campaign):
	ensure_default_sources()
	lead = frappe.get_doc(
		{
			"doctype": "Lead",
			"client": client,
			"source": source,
			"campaign": campaign or None,
			"consent_status": consent.UNKNOWN,
		}
	)
	lead.flags.ignore_permissions = True
	return lead.insert().name


def _save_evidence(lead, kind, reference, evidence) -> str:
	"""The raw event or submission as a private file. Returns its address, which the Consent Record keeps."""
	body = json.dumps(evidence, sort_keys=True, indent=1, default=str).encode()
	saved = save_file(f"{kind}-{reference}.json", body, "Lead", lead, is_private=1)
	return saved.file_url


def _log_activity(lead, activity_type, notes):
	frappe.get_doc(
		{
			"doctype": "Lead Activity",
			"lead": lead,
			"activity_type": activity_type,
			"activity_date": now_datetime(),
			"notes": notes,
		}
	).insert(ignore_permissions=True)


def take(
	*,
	phone,
	source,
	kind,
	reference,
	evidence,
	name=None,
	email=None,
	campaign=None,
	notes=None,
	stop_source=None,
	activity_type=NOTE,
) -> dict:
	"""Make or merge the lead of one person who reached us, and record their consent or stop request.

	phone: the person's number, in any form. source: a Lead Source name. kind and reference name the
	evidence file (`<kind>-<reference>.json`). evidence: the raw event or submission, saved as a private
	file. stop_source: set it (one of consent.STOP_SOURCES) when the person asked us to stop. Returns
	{"lead", "client", "created", "merged", "stop", "consent_record"}."""
	number = normalise_phone(phone)
	if not number:
		frappe.throw(_("A phone number is needed."), frappe.ValidationError)
	client, lead = _find_lead(number, email)
	created = not lead
	if created:
		label = (name or "").strip() or _("Caller {0}").format(number[-3:])
		client = client or _new_client(label, number, email)
		lead = _new_lead(client, source, campaign)
	file_url = _save_evidence(lead, kind, reference, evidence)
	record = None
	if stop_source:
		consent.record_opt_out(lead, stop_source)
		_log_activity(
			lead, activity_type, notes or _("Asked to stop being contacted ({0}).").format(stop_source)
		)
	else:
		record = (
			frappe.get_doc(
				{
					"doctype": "Consent Record",
					"lead": lead,
					"basis": "Inquiry",
					"recorded_on": now_datetime(),
					"evidence_link": file_url,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		_log_activity(lead, activity_type, notes)
		consent.sync_lead_status(lead)
	return {
		"lead": lead,
		"client": client,
		"created": created,
		"merged": not created,
		"stop": bool(stop_source),
		"consent_record": record,
	}
