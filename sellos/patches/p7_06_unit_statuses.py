# SOS-P7-06 adds Booked and Blocked to a unit's statuses, the hold fields to the unit and the company
# setting "Unit hold hours". Reloading the Unit DocType adds the options and the columns and changes no
# existing unit: each keeps its status, and a Held unit with no hold end time is left as it is. The hold
# hours default is set only where it is blank. Running it again changes nothing.
import frappe


def execute():
	frappe.reload_doc("sellos", "doctype", "unit")
	frappe.reload_doc("sellos", "doctype", "sellos_settings")
	if not frappe.db.get_single_value("SellOS Settings", "unit_hold_hours"):
		frappe.db.set_single_value("SellOS Settings", "unit_hold_hours", 48)
