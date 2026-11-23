# SOS-P7-04 adds the Commission Rate, Commission Payout and Commission Statement Export DocTypes to a site that
# already runs. Running it again changes nothing.
import frappe


def execute():
	for doctype in ("commission_rate", "commission_payout", "commission_statement_export"):
		frappe.reload_doc("sellos", "doctype", doctype)
