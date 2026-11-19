# SOS-P1-25 names the outcome of a site visit `visit_outcome`, so no other DocType has a field called
# `outcome` that is not the Call Outcome link (SOS-P1-21). A site that already holds the old column
# moves its values across. Running it again changes nothing.
import frappe


def execute():
	frappe.reload_doc("sellos", "doctype", "site_visit")
	if frappe.db.has_column("Site Visit", "outcome"):
		frappe.db.sql("update `tabSite Visit` set visit_outcome = outcome where ifnull(outcome, '') != ''")
