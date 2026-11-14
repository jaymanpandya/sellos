# SOS-P1-16 adds the normalised phone keys and merged_into to the Client on every company site. The
# patch loads the new definition and fills the keys of existing clients. It changes no other field
# and keeps each client's modified time. Running it again changes nothing.
import frappe

from sellos.crm.duplicates import normalise_phone


def execute():
	frappe.reload_doc("sellos", "doctype", "client")
	for row in frappe.get_all("Client", fields=["name", "phone", "overseas_phone"]):
		frappe.db.set_value(
			"Client",
			row.name,
			{
				"phone_key": normalise_phone(row.phone),
				"overseas_phone_key": normalise_phone(row.overseas_phone),
			},
			update_modified=False,
		)
