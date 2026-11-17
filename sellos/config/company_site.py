"""The setup every company site gets (P1.06A). Provisioning and the test site both call this.

It is safe to run again. It creates the five roles and gives SellOS Settings a company name, so the
web app shows the company and never the site's address.
"""

import frappe

from sellos.access.roles import ensure_roles
from sellos.crm.lead_sources import ensure_default_sources
from sellos.crm.pipeline import ensure_default_stages

DEFAULT_COMPANY_NAME = "Pandya Realtors"


def configure_company_site(company_name: str | None = None) -> dict:
	"""Make the site ready for a company. Returns the settings it left in place."""
	ensure_roles()
	ensure_default_sources()  # SOS-P1-20
	ensure_default_stages()  # SOS-P1-07
	settings = frappe.get_doc("SellOS Settings")
	if company_name or not settings.company_name:
		settings.company_name = company_name or DEFAULT_COMPANY_NAME
		settings.save(ignore_permissions=True)
		frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
	return {"company_name": settings.company_name, "logo": settings.logo or ""}
