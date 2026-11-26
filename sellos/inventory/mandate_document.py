"""The mandate document that goes out for signing (SOS-LOOP).

Built from the mandate template below with the company's branding (logo, colours, name, RERA number, footer), the
seller, the property, the fee, the term, the exclusivity and the signers. The clauses are a plain starting wording,
NOT legal advice: counsel decides the final text (docs/DOCUSEAL.md). The function returns the PDF bytes and where
the two signature boxes are, so the signing service can place its fields on them.
"""

import frappe
from frappe.utils import format_date

from sellos.inventory import branding
from sellos.inventory.pdf_writer import MARGIN, MUTED, PAGE_H, PAGE_W, Document

TITLE = "Mandate to sell property"
SIGNATURE_BOX = (210, 64)  # width and height, in points

EXCLUSIVE_CLAUSE = (
	"Exclusive mandate: for the term of this mandate the Owner appoints the Company as the only agent to sell the "
	"Property. The Owner will not appoint another agent and will send every enquiry to the Company."
)
OPEN_CLAUSE = (
	"Open mandate: the Owner appoints the Company to sell the Property and may appoint other agents too. The Company "
	"earns its fee only on a sale it brings about."
)
CLAUSES = (
	"The Owner confirms that they own the Property or are authorised to sell it, and that the information they have "
	"given about it is true.",
	"The Company will market the Property, show it to buyers and keep the Owner informed of every offer.",
	"The Owner will pay the Company the fee stated above, as a percentage of the sale price, when a sale of the "
	"Property is completed during the term or to a buyer the Company introduced.",
	"Either party may end this mandate before the end of its term by writing to the other. The fee remains due on "
	"a sale to a buyer introduced before it ended.",
)


def view(doc, signers) -> dict:
	"""What the document states, as data."""
	lead = frappe.get_doc("Lead", doc.lead)
	client = frappe.db.get_value("Client", lead.client, ["client_name", "city"], as_dict=True) or {}
	prop = (
		frappe.db.get_value(
			"Property",
			lead.get("property"),
			[
				"title",
				"property_type",
				"locality",
				"city",
				"address",
				"configuration",
				"carpet_area",
				"rera_number",
			],
			as_dict=True,
		)
		if lead.get("property")
		else None
	)
	return {
		"brand": branding.brand(),
		"mandate": doc.name,
		"type": doc.mandate_type,
		"start_date": format_date(doc.start_date, "dd MMM yyyy"),
		"ends_on": format_date(doc.ends_on, "dd MMM yyyy"),
		"term_months": doc.term_months,
		"fee_percent": doc.fee_percent,
		"owner": client.get("client_name") or doc.lead,
		"owner_city": client.get("city") or "",
		"property": prop,
		"signers": signers,
	}


def build(v) -> tuple[bytes, list[dict]]:
	"""The mandate document and its signature fields: [{role, page, x, y, w, h}] with positions from 0 to 1, measured
	from the top left of the page, as the signing service expects."""
	b = v["brand"]
	pdf = Document(b, TITLE)
	page = pdf.new_page()
	pdf.y = PAGE_H - 78
	page.text(MARGIN, pdf.y, TITLE, 20, True, pdf.primary)
	pdf.y -= 8
	page.rule(pdf.y, pdf.accent, 1.5)
	pdf.y -= 8
	pdf.para(f"Mandate {v['mandate']}", 10, MUTED, gap=8)

	pdf.subheading("Parties")
	pdf.pair("Owner", v["owner"] + (f", {v['owner_city']}" if v["owner_city"] else ""))
	company = b["name"] or "the Company"
	pdf.pair("Company", company + (f" (RERA {b['rera_number']})" if b["rera_number"] else ""))
	if b["address"]:
		pdf.pair("Company address", b["address"])

	pdf.subheading("Property")
	p = v["property"]
	if p:
		pdf.pair("Property", p.get("title") or "-")
		pdf.pair(
			"Address", " ".join(x for x in (p.get("address"), p.get("locality"), p.get("city")) if x) or "-"
		)
		if p.get("configuration") or p.get("carpet_area"):
			area = f"{p['carpet_area']:g} sq ft carpet" if p.get("carpet_area") else ""
			pdf.pair("Details", ", ".join(x for x in (p.get("configuration"), area) if x))
		if p.get("rera_number"):
			pdf.pair("RERA number", p["rera_number"])
	else:
		pdf.pair("Property", "To be identified by the Owner and the Company before the sale.")

	pdf.subheading("Terms")
	pdf.pair("Type", v["type"])
	pdf.pair("Term", f"{v['term_months']} months, from {v['start_date']} to {v['ends_on']}")
	pdf.pair("Fee", f"{v['fee_percent']:g}% of the sale price")

	pdf.subheading("Conditions")
	pdf.para(EXCLUSIVE_CLAUSE if v["type"] == "Exclusive" else OPEN_CLAUSE, gap=6)
	for number, clause in enumerate(CLAUSES, 1):
		pdf.para(f"{number}. {clause}", gap=6)

	pdf.subheading("Signers")
	for s in v["signers"]:
		pdf.pair(s["role"], f"{s['name']} ({s['email']})")

	width, height = SIGNATURE_BOX
	pdf.need(height + 70)
	pdf.space(14)
	top = pdf.y
	fields = []
	for column, s in enumerate(v["signers"]):
		x = MARGIN + column * (width + 40)
		pdf.page.text(x, top, f"{s['role']} signature: {s['name']}", 9.5, True, MUTED)
		bottom = top - 8 - height
		pdf.page.rule(bottom, pdf.accent, 0.8, x, x + width)
		fields.append(
			{
				"role": s["role"],
				"page": len(pdf.pages),
				"x": round(x / PAGE_W, 4),
				"y": round((PAGE_H - (bottom + height)) / PAGE_H, 4),
				"w": round(width / PAGE_W, 4),
				"h": round(height / PAGE_H, 4),
			}
		)
	pdf.y = top - height - 24
	pdf.para(
		"This is an electronic signature on an electronic document. Each signer's name, time and address are kept in "
		"the audit trail of the signing service.",
		8.5,
		MUTED,
	)
	return pdf.to_bytes(), fields
