# SOS-P1-07 carries a company's stages and leads over to the eleven stage buyer pipeline: Site visit
# scheduled becomes Site visit booked, Booked becomes Booking, Lost becomes Closed lost, the stages the
# old list lacked are added, and a lead with no stage goes on the first one. Running it again changes nothing.
import frappe

from sellos.crm.pipeline import carry_over_stages


def execute():
	frappe.reload_doc("sellos", "doctype", "lead_stage_change")
	frappe.reload_doc("sellos", "doctype", "pipeline_stage")
	frappe.reload_doc("sellos", "doctype", "lead")
	carry_over_stages()
