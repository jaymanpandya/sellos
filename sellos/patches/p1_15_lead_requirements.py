# SOS-P1-15 adds the requirement fields to the Lead on every company site. The patch only loads the new
# Lead definition, so the columns exist. It writes no lead row: existing leads keep every value and keep
# their modified time. Running it again changes nothing.
import frappe


def execute():
	frappe.reload_doc("sellos", "doctype", "lead")
