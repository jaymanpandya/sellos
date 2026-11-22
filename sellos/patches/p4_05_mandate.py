# SOS-P4-05 adds the Mandate DocType and its two child tables to a site that already runs. Running it again
# changes nothing.
import frappe


def execute():
	for doctype in ("mandate_dossier_item", "mandate_dossier_view", "mandate"):
		frappe.reload_doc("sellos", "doctype", doctype)
