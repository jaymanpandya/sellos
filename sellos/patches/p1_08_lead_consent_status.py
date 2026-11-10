# P1.08 leads made before the Consent Record have no consent status. They have no live record: Unknown.
import frappe


def execute():
	frappe.db.sql(
		"update `tabLead` set consent_status = 'Unknown' where consent_status is null or consent_status = ''"
	)
