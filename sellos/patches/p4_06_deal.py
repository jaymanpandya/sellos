# SOS-P4-06 adds the Deal DocType and its Commission Split child table to a site that already runs. Running it
# again changes nothing.
import frappe


def execute():
	for doctype in ("commission_split", "deal"):
		frappe.reload_doc("sellos", "doctype", doctype)
