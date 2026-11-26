# SOS-LOOP (25 Nov 2026): a lead's stored title is the person's plain name, not "Name Source", and a signed
# mandate with no DocuSeal submission is "Signed offline", not "Not sent". Both are rewritten only where they are
# still the old value, so running the patch again changes nothing. Modified times are kept.
import frappe


def execute():
	frappe.reload_doc("sellos", "doctype", "mandate")
	rows = frappe.db.sql(
		"""select lead.name, client.client_name from `tabLead` lead
		join `tabClient` client on client.name = lead.client
		where lead.source is not null and lead.source != ''
		and lead.lead_title = concat(client.client_name, ' ', lead.source)""",
		as_dict=True,
	)
	for row in rows:
		frappe.db.set_value("Lead", row.name, "lead_title", row.client_name, update_modified=False)
	for name in frappe.get_all(
		"Mandate",
		filters={"status": "Signed", "signing_status": ["in", ["Not sent", ""]]},
		pluck="name",
	):
		frappe.db.set_value("Mandate", name, "signing_status", "Signed offline", update_modified=False)
