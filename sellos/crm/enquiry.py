"""The enquiry page (SOS-P2-08): a link a bought lead gets through WhatsApp or an ad.

The page (`www/enquiry.html`) shows the company's consent wording and a short form. Its submit method is
the first public intake method (`sellos.access.public_intake`): it checks the form key, the limits, the
honeypot and the fields, then makes or merges the lead through `sellos.crm.intake.take`, which records an
inquiry Consent Record (7 days) whose evidence is the wording shown, its version, the time, the address and
the submission, saved as a private file. A person who ticks "Stop contacting me" is recorded as Opted out
instead. Consent never blocks, so neither outcome stops a later call or SMS (only a WhatsApp STOP stops what is sent on WhatsApp unprompted).

The wording is the company setting "Consent wording" (SellOS Settings), which a Company Admin edits and
which also shows to channel partners (SOS-P7-02). The form key is in the link, and a Company Admin rotates
it here.
"""

import hashlib
from urllib.parse import quote

import frappe
from frappe.utils import get_url, now

from sellos.access.partner_registrations import consent_wording
from sellos.access.public_intake import Field, IntakeRequest, form_key, public_intake, rotate_form_key
from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.crm import intake
from sellos.crm.lead_sources import WEBSITE

PAGE_PATH = "/enquiry"
CAMPAIGN = "Enquiry page"
MAX_BODY_BYTES = 8 * 1024
PER_ADDRESS_PER_MINUTE = 10
PER_TENANT_PER_MINUTE = 120
HONEYPOT = "website"

FIELDS = {
	"name": Field(max_length=100, required=True),
	"phone": Field(max_length=20, required=True, pattern=r"[0-9+()\- ]{7,20}"),
	"email": Field(max_length=140, pattern=r"[^@\s]+@[^@\s]+\.[^@\s]+"),
	"message": Field(max_length=1000),
	"stop": Field(kind="flag"),
}


def wording_version(wording: str) -> str:
	"""A short version id of the wording: it changes whenever the words change."""
	return "w-" + hashlib.sha256(wording.encode()).hexdigest()[:8]


def page_link() -> str:
	"""The link to share: the enquiry page with this company's form key."""
	return f"{get_url()}{PAGE_PATH}?k={quote(form_key())}"


@public_intake(
	fields=FIELDS,
	honeypot_field=HONEYPOT,
	max_body_bytes=MAX_BODY_BYTES,
	rate_limit_per_address=PER_ADDRESS_PER_MINUTE,
	rate_limit_per_tenant=PER_TENANT_PER_MINUTE,
	consent_evidence=(
		"The consent wording shown, its version, the time, the caller's address and the submission, saved "
		"as a private file and linked as the inquiry Consent Record's evidence."
	),
	calls_intake="sellos.crm.intake.take",
)
def submit_enquiry(request: IntakeRequest):
	"""Take one enquiry or stop request from the page. The answer is only a thank you and a reference."""
	fields = request.fields
	wording = consent_wording()
	evidence = {
		"page": "enquiry",
		"wording": wording,
		"wording_version": wording_version(wording),
		"shown_and_submitted_on": now(),
		"address": request.address,
		"submitted": {key: value for key, value in fields.items()},
	}
	intake.take(
		phone=fields["phone"],
		source=WEBSITE,
		campaign=CAMPAIGN,
		kind="enquiry",
		reference=request.reference,
		evidence=evidence,
		name=fields["name"],
		email=fields["email"],
		notes=fields["message"] or "Sent the enquiry page.",
		stop_source="Website" if fields["stop"] else None,
	)


# --- a Company Admin's view of the page ------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def get_enquiry_settings():
	"""The link to share, the wording shown on the page and its version."""
	wording = consent_wording()
	return {"link": page_link(), "consent_wording": wording, "wording_version": wording_version(wording)}


@sellos_api(COMPANY_ADMIN)
def rotate_enquiry_key():
	"""Make a new form key. Links shared before this stop working."""
	rotate_form_key()
	return get_enquiry_settings()
