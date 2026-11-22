# SOS-P4-04 adds the pipeline field to Pipeline Stage and Lead. Every stage and lead that has none is the
# Buyer's, and the ten seller stages are seeded. Running it again changes nothing.
import frappe

from sellos.crm import pipeline


def execute():
	frappe.reload_doc("sellos", "doctype", "pipeline_stage")
	frappe.reload_doc("sellos", "doctype", "lead")
	frappe.db.sql(
		"update `tabPipeline Stage` set pipeline = %s where pipeline is null or pipeline = ''",
		(pipeline.BUYER,),
	)
	frappe.db.sql(
		"update `tabLead` set pipeline = %s where pipeline is null or pipeline = ''", (pipeline.BUYER,)
	)
	pipeline.ensure_default_stages(pipeline.SELLER)
