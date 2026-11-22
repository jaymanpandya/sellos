"""The Channel Partner's reports (SOS-P5-03).

A partner sees only their own data. Their leads are read through `frappe.get_list`, so the lead permission
rules decide the rows (the leads they registered or hold, and none at all while their firm is not Approved),
and the report adds no rule of its own that could widen them. The method refuses any login that is not a
pure partner login, so a person who is also an Agent or Company Admin cannot read the wider scope through it.

* **Leads.** The partner's own leads created in the dates, by stage, and the list behind the figures. A
  lead is listed by its title and stage. No phone number is read, listed or sent.
* **Deals and commission statements.** Panels that wait for SOS-P4-06 and SOS-P7-04 (see `panels.py`). A
  partner's reader is told the firm and the user and returns only theirs.
"""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days

from sellos.access.partner_firms import FIRM, firm_of, is_pure_partner
from sellos.access.registry import sellos_api
from sellos.access.roles import CHANNEL_PARTNER
from sellos.reports.engine import MAX_RECORDS, _range
from sellos.reports.panels import run_panel

PANELS = (
	{
		"key": "deals",
		"title": "Deals",
		"description": "The deals on the buyers your firm registered.",
		"reader": "sellos.crm.partner_panels.deals",
		"waiting": "Deals will appear here once the company records them.",
	},
	{
		"key": "commission",
		"title": "Commission statements",
		"description": "What the company owes your firm and has paid, by payout.",
		"reader": "sellos.crm.partner_panels.commission",
		"waiting": "Commission statements will appear here once the company records payouts.",
	},
)


@sellos_api(CHANNEL_PARTNER)
def partner_report(from_date=None, to_date=None):
	"""The signed in partner's own leads by stage for a range of dates, and their deal and commission panels."""
	user = frappe.session.user
	if not is_pure_partner(frappe.get_roles(user)):
		frappe.throw(_("This report is for a channel partner login."), frappe.PermissionError)
	start, end = _range(from_date, to_date)
	firm = firm_of(user)
	leads = frappe.get_list(
		"Lead",
		filters=[
			["archived", "=", 0],
			["creation", ">=", f"{start} 00:00:00"],
			["creation", "<", f"{add_days(end, 1)} 00:00:00"],
		],
		fields=["name", "lead_title", "stage", "creation"],
		order_by="creation desc, name desc",
		limit_page_length=0,
	)
	by_stage = Counter(lead.stage or "" for lead in leads)
	shown = leads[:MAX_RECORDS]
	return {
		"from_date": str(start),
		"to_date": str(end),
		"firm": {"name": firm, "firm_name": frappe.db.get_value(FIRM, firm, "firm_name")} if firm else None,
		"leads": {
			"total": len(leads),
			"by_stage": [
				{"stage": stage, "label": stage or _("Not set"), "count": count}
				for stage, count in sorted(by_stage.items(), key=lambda item: (-item[1], item[0]))
			],
			"records": [
				{
					"name": lead.name,
					"title": lead.lead_title or lead.name,
					"stage": lead.stage or "",
					"created": str(lead.creation)[:10],
				}
				for lead in shown
			],
			"shown": len(shown),
			"truncated": len(leads) > len(shown),
		},
		"panels": [run_panel(panel, start, end, firm=firm, user=user) for panel in PANELS],
	}
