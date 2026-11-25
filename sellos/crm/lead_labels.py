"""The plain name of a lead and its source, kept apart (SOS-LOOP, 25 Nov 2026).

A lead's stored title is the client's name followed by its source ("Asha Rao Website"). A screen that
lists leads shows the plain name, with the source in its own muted field, never joined to the name.
`add` puts `lead_name` and `lead_source` on every row that has a `lead` key, in two queries.
`lead_title` is left as it was, because reports and tests read it.
"""

import frappe


def add(rows, key="lead") -> None:
	names = {row.get(key) for row in rows if row.get(key)}
	if not names:
		return
	leads = frappe.get_all(
		"Lead",
		filters={"name": ["in", sorted(names)]},
		fields=["name", "client", "source", "lead_title"],
		limit_page_length=0,
	)
	clients = dict(
		frappe.get_all(
			"Client",
			filters={"name": ["in", sorted({lead.client for lead in leads if lead.client})]},
			fields=["name", "client_name"],
			as_list=True,
			limit_page_length=0,
		)
	)
	by_lead = {lead.name: lead for lead in leads}
	for row in rows:
		if not row.get(key):
			continue
		lead = by_lead.get(row.get(key))
		row["lead_name"] = (clients.get(lead.client) if lead else None) or (lead.lead_title if lead else "")
		row["lead_source"] = (lead.source if lead else "") or ""
