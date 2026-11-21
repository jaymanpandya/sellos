"""The enquiry page (SOS-P2-08). A guest may open it: it shows the company's name, its consent wording and a
form, and reads no record. The submit method is `sellos.crm.enquiry.submit_enquiry`."""

import frappe

from sellos.access.partner_registrations import consent_wording
from sellos.spa import get_company_branding

no_cache = 1


def get_context(context):
	branding = get_company_branding()
	context.no_cache = 1
	context.company = branding["name"] or "the company"
	context.logo = branding["logo"]
	context.consent_wording = consent_wording()
	context.key = frappe.form_dict.get("k") or ""
	context.method = "sellos.crm.enquiry.submit_enquiry"
	return context
