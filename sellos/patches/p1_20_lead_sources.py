# SOS-P1-20 replaces the free text source of every lead with a source from the Lead Source list. The
# eight standard sources are made, a value that names one maps to it, a value no source matches becomes a
# new source, and a lead with no value gets Not recorded. Running it again changes nothing.
import frappe

from sellos.crm.lead_sources import map_free_text_sources


def execute():
	frappe.reload_doc("sellos", "doctype", "lead_source")
	frappe.reload_doc("sellos", "doctype", "lead")
	map_free_text_sources()
