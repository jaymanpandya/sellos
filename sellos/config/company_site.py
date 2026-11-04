"""The setup every company site gets (P1.06A). Provisioning and the test site both call this.

It is safe to run again. It creates the five roles and gives SellOS Settings a company name, so the
web app shows the company and never the site's address.
"""

import frappe

from sellos.access.roles import ensure_roles

DEFAULT_COMPANY_NAME = "Pandya Realtors"


def configure_company_site(company_name: str | None = None) -> dict:
	"""Make the site ready for a company. Returns the settings it left in place."""
	ensure_roles()
	settings = frappe.get_doc("SellOS Settings")
	if company_name or not settings.company_name:
		settings.company_name = company_name or DEFAULT_COMPANY_NAME
		settings.save(ignore_permissions=True)
		frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
	return {"company_name": settings.company_name, "logo": settings.logo or ""}
