"""The website lead endpoint (SOS-P1-09).

The company's website posts each enquiry here, over HTTPS, with the company's "Lead intake" key. It is a
public intake method (`sellos.access.public_intake`): the shared checks (body cap, limits per address and
per tenant, honeypot, strict fields, the key) run first, then `sellos.crm.intake.take` makes or merges the
lead. It builds no second intake path.

* A submission with consent wording makes an inquiry Consent Record (7 days), with the wording the
  website showed, its version, the time and the address saved as a private evidence file, and the lead is
  Consented.
* A submission without wording is still accepted (consent never blocks, Jayman, 10 November 2026): the
  lead is made or merged with its consent status Unknown, no Consent Record is made and a Lead Activity
  records the warning.

The key is made by a Company Admin (`rotate_website_key`) and shown once: only its hash is kept.
"""

import frappe
from frappe import _
from frappe.utils import get_url, now

from sellos.access import intake_keys
from sellos.access.public_intake import Field, IntakeRequest, public_intake
from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.crm import intake
from sellos.crm.enquiry import wording_version
from sellos.crm.lead_sources import WEBSITE

CAMPAIGN = "Website form"
MAX_BODY_BYTES = 16 * 1024
# The website's server sends every visitor's form from one address, so the address limit is higher than
# the enquiry page's.
PER_ADDRESS_PER_MINUTE = 60
PER_TENANT_PER_MINUTE = 300
HONEYPOT = "company_url"
SUBMIT_PATH = "/api/method/sellos.crm.website_form.submit_website_lead"
NO_WORDING_WARNING = "Website enquiry came with no consent wording. Consent status: Unknown."

FIELDS = {
	"name": Field(max_length=100, required=True),
	"phone": Field(max_length=20, required=True, pattern=r"[0-9+()\- ]{7,20}"),
	"email": Field(max_length=140, pattern=r"[^@\s]+@[^@\s]+\.[^@\s]+"),
	"message": Field(max_length=1000),
	"form": Field(max_length=100),  # which form of the website sent it
	"consent_wording": Field(max_length=2000),  # the words the visitor saw next to the form
	"stop": Field(kind="flag"),
}


@public_intake(
	fields=FIELDS,
	honeypot_field=HONEYPOT,
	max_body_bytes=MAX_BODY_BYTES,
	rate_limit_per_address=PER_ADDRESS_PER_MINUTE,
	rate_limit_per_tenant=PER_TENANT_PER_MINUTE,
	consent_evidence=(
		"The consent wording the website showed, its version, the time, the caller's address and the "
		"submission, saved as a private file and linked as the inquiry Consent Record's evidence."
	),
	calls_intake="sellos.crm.intake.take",
	key_scope=intake_keys.LEAD_INTAKE,
)
def submit_website_lead(request: IntakeRequest):
	"""Take one website enquiry. The answer is only a thank you and a reference."""
	fields = request.fields
	wording = fields["consent_wording"]
	evidence = {
		"page": fields["form"] or "website",
		"wording": wording,
		"wording_version": wording_version(wording) if wording else "",
		"shown_and_submitted_on": now(),
		"address": request.address,
		"submitted": dict(fields),
	}
	stop = bool(fields["stop"])
	notes = fields["message"] or _("Sent the website form.")
	if not wording and not stop:
		notes = f"{_(NO_WORDING_WARNING)} {notes}"
	intake.take(
		phone=fields["phone"],
		source=WEBSITE,
		campaign=CAMPAIGN,
		kind="website",
		reference=request.reference,
		evidence=evidence,
		name=fields["name"],
		email=fields["email"],
		notes=notes,
		stop_source="Website" if stop else None,
		has_consent=bool(wording),
	)


# --- a Company Admin's view of the endpoint ---------------------------------------------------------------


def _settings(key=None) -> dict:
	out = {
		"endpoint": f"{get_url()}{SUBMIT_PATH}",
		"keys": intake_keys.active_keys(intake_keys.LEAD_INTAKE),
	}
	if key:
		out["key"] = key  # shown once: only its hash is kept
	return out


@sellos_api(COMPANY_ADMIN)
def get_website_settings():
	"""The endpoint address and the keys made so far (label and state only, never a key)."""
	return _settings()


@sellos_api(COMPANY_ADMIN)
def rotate_website_key():
	"""Make a new Lead intake key and switch off the old ones. The new key is in the answer once."""
	return _settings(intake_keys.make_key(intake_keys.LEAD_INTAKE, "Website form", replace=True))
