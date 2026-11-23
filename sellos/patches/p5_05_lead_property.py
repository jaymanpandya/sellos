# SOS-P5-05 adds the optional Property link to the Lead on every company site. The patch only loads the new
# Lead definition, so the column exists. It writes no lead row and backfills nothing: existing leads keep
# every value and keep their modified time. Running it again changes nothing.
import frappe


def execute():
	frappe.reload_doc("sellos", "doctype", "lead")
