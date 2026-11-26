"""The Private Sale Dossier as a branded PDF (SOS-LOOP).

The PDF has the company's branding (logo, colours, name, footer text), a cover page, the seller and property
summary, the mandate and its signing status, the notes grouped by type with their images embedded and their
documents listed, the dossier's own notes and files, and "Page N of M" on every page. It is made on the server,
stored as a private file of the mandate with a version number, and regenerated on request: each version is kept.

It follows the Dossier's release rule (SOS-SETUP-34): it is made, listed and opened only while the mandate is signed
and not archived. It holds no phone number and no email address, which the people who may open the Dossier may not
all see in full. With no branding set it uses the clean default look (sellos.inventory.branding).
"""

import frappe
from frappe import _
from frappe.utils import format_datetime, get_datetime, now_datetime

from sellos.inventory import branding
from sellos.inventory.pdf_writer import MARGIN, MUTED, PAGE_H, PAGE_W, Document

TITLE = "Private Sale Dossier"
DOSSIER_PDF_FIELD = "dossier_pdf"
IMAGES_PER_NOTE = 6


def _when(value) -> str:
	return format_datetime(get_datetime(value), "dd MMM yyyy, HH:mm") if value else "-"


_file_bytes = branding.file_bytes


def _is_image(name) -> bool:
	return str(name or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp"))


def view(doc, version) -> dict:
	"""Everything the PDF shows, as data (so a test can read it without parsing the PDF)."""
	from sellos.crm import notes as notes_module

	lead = frappe.get_doc("Lead", doc.lead)
	client = frappe.db.get_value("Client", lead.client, ["client_name", "city"], as_dict=True) or {}
	prop = (
		frappe.db.get_value(
			"Property",
			lead.get("property"),
			["title", "property_type", "locality", "city", "configuration", "carpet_area", "rera_number"],
			as_dict=True,
		)
		if lead.get("property")
		else None
	)
	people = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	order = {t["name"]: i for i, t in enumerate(notes_module._types(only_shown=False))}
	groups: dict[str, list] = {}
	for note in sorted(notes_module.notes_for(lead=doc.lead), key=lambda n: n["created"]):
		groups.setdefault(note["type_label"], []).append(note)
	ordered = sorted(groups.items(), key=lambda kv: order.get(kv[1][0]["note_type"], 999))
	return {
		"brand": branding.brand(),
		"version": version,
		"made_on": _when(now_datetime()),
		"mandate": {
			"name": doc.name,
			"type": doc.mandate_type,
			"start_date": str(doc.start_date or ""),
			"ends_on": str(doc.ends_on or ""),
			"term_months": doc.term_months,
			"fee_percent": doc.fee_percent,
			"status": doc.status,
			"signed_on": _when(doc.signed_on) if doc.signed_on else "",
			"signing_status": doc.signing_status or "Not sent",
			"signers": [
				{
					"role": s.role,
					"name": s.signer_name or "",
					"status": s.status,
					"viewed_on": _when(s.viewed_on) if s.viewed_on else "",
					"completed_on": _when(s.completed_on) if s.completed_on else "",
				}
				for s in doc.signers
			],
		},
		"seller": {
			"name": client.get("client_name") or doc.lead,
			"city": client.get("city") or "",
			"source": lead.source or "",
			"agent": people.get(lead.assigned_to, lead.assigned_to or ""),
			"lead": doc.lead,
		},
		"property": prop,
		"notes": [{"type": label, "notes": rows} for label, rows in ordered],
		"items": [
			{
				"kind": i.kind,
				"title": i.title,
				"note": i.note or "",
				"file": i.file or "",
				"added_by": people.get(i.added_by, i.added_by or ""),
				"added_on": _when(i.added_on),
			}
			for i in doc.dossier
		],
	}


def _cover(pdf: Document, v):
	b = v["brand"]
	page = pdf.new_page(cover=True)
	page.rect(0, PAGE_H - 330, PAGE_W, 330, pdf.primary)
	page.rect(0, PAGE_H - 336, PAGE_W, 6, pdf.accent)
	y = PAGE_H - 70
	logo = branding.logo_bytes(b["logo"])
	if logo:
		page.rect(MARGIN - 10, y - 66, 190, 76, (1, 1, 1))
		pdf.y = y
		before = len(pdf.images)
		from sellos.inventory.pdf_writer import prepare_image

		prepared = prepare_image(logo)
		if prepared:
			jpeg, (w, h) = prepared
			scale = min(170 / w, 56 / h, 1.0)
			pdf.images.append((jpeg, (w, h)))
			page.image(before, MARGIN, y - 56 + (56 - h * scale) / 2, w * scale, h * scale)
	name = b["name"]
	if name:
		page.text(MARGIN, PAGE_H - 175, name, 22, True, (1, 1, 1))
	page.text(MARGIN, PAGE_H - 235, TITLE, 30, True, (1, 1, 1))
	subject = (v["property"] or {}).get("title") or v["seller"]["name"]
	page.text(MARGIN, PAGE_H - 268, subject, 15, False, (1, 1, 1))
	page.text(MARGIN, PAGE_H - 296, f"Seller: {v['seller']['name']}", 11, False, (1, 1, 1))
	page.text(MARGIN, PAGE_H - 380, f"Mandate {v['mandate']['name']}", 12, True, pdf.primary)
	page.text(MARGIN, PAGE_H - 400, f"Version {v['version']}, made on {v['made_on']}", 10.5, False, MUTED)
	page.text(MARGIN, PAGE_H - 418, f"Signing status: {v['mandate']['signing_status']}", 10.5, False, MUTED)
	y = 190
	for line in (
		b["address"],
		" | ".join(p for p in (b["phone"], b["email"], b["website"]) if p),
		f"RERA registration {b['rera_number']}" if b["rera_number"] else "",
	):
		if line:
			page.text(MARGIN, y, line[:100], 10, False, MUTED)
			y -= 16
	pdf.y = 0


def _summary(pdf: Document, v):
	s, p = v["seller"], v["property"]
	pdf.new_page()
	pdf.heading("Seller and property")
	pdf.pair("Seller", s["name"])
	pdf.pair("City", s["city"] or "-")
	pdf.pair("Source", s["source"] or "-")
	pdf.pair("Handled by", s["agent"] or "-")
	pdf.space(6)
	pdf.subheading("Property")
	if p:
		facts = [
			("Title", p.get("title")),
			("Type", p.get("property_type")),
			("Locality", " ".join(x for x in (p.get("locality"), p.get("city")) if x)),
			("Configuration", p.get("configuration")),
			("Carpet area", f"{p['carpet_area']:g} sq ft" if p.get("carpet_area") else ""),
			("RERA number", p.get("rera_number")),
		]
		for label, value in facts:
			pdf.pair(label, value or "-")
	else:
		pdf.para("No property is linked to this seller yet.", colour=MUTED)


def _mandate(pdf: Document, v):
	m = v["mandate"]
	pdf.heading("Mandate and signing")
	pdf.pair("Type", m["type"])
	pdf.pair("Term", f"{m['term_months']} months, from {m['start_date']} to {m['ends_on']}")
	pdf.pair("Fee", f"{m['fee_percent']:g}% of the sale price")
	pdf.pair("Status", m["status"] + (f", on {m['signed_on']}" if m["signed_on"] else ""))
	pdf.pair("Electronic signing", m["signing_status"])
	for signer in m["signers"]:
		line = f"{signer['name'] or signer['role']} ({signer['role']}): {signer['status']}"
		if signer["completed_on"]:
			line += f", signed {signer['completed_on']}"
		elif signer["viewed_on"]:
			line += f", viewed {signer['viewed_on']}"
		pdf.pair("Signer", line)


def _notes(pdf: Document, v):
	pdf.heading("Notes")
	if not v["notes"]:
		pdf.para("No notes have been written yet.", colour=MUTED)
	for group in v["notes"]:
		pdf.subheading(f"{group['type']} ({len(group['notes'])})")
		for note in group["notes"]:
			pdf.para(f"{note['author_name']}, {_when(note['created'])}", 9, MUTED, gap=2)
			if note["body"]:
				pdf.para(note["body"], 10, indent=8)
			images = [a for a in note["attachments"] if a["kind"] == "Image"][:IMAGES_PER_NOTE]
			pictures = [c for c in (_file_bytes(a["file"]) for a in images) if c]
			if pictures:
				pdf.space(2)
				pdf.pictures(pictures)
			for a in note["attachments"]:
				if a["kind"] != "Image":
					pdf.para(f"Document: {a['file_name']}", 9.5, indent=8, gap=2)
			pdf.space(5)


def _items(pdf: Document, v):
	pdf.heading("Dossier notes and files")
	if not v["items"]:
		pdf.para("Nothing has been added to the dossier itself.", colour=MUTED)
	for item in v["items"]:
		pdf.para(
			f"{item['title']}  ({item['kind']}, {item['added_by']}, {item['added_on']})", 10, bold=True, gap=2
		)
		if item["kind"] == "Note":
			pdf.para(item["note"], 10, indent=8)
		else:
			content = _file_bytes(item["file"]) if _is_image(item["file"]) else None
			if content:
				pdf.pictures([content], (240, 170))
			else:
				pdf.para("File: " + item["file"].rsplit("/", 1)[-1], 9.5, indent=8)
		pdf.space(4)


def build(v) -> bytes:
	b = v["brand"]
	pdf = Document(b, TITLE)
	_cover(pdf, v)
	_summary(pdf, v)
	_mandate(pdf, v)
	_notes(pdf, v)
	_items(pdf, v)
	return pdf.to_bytes()


def generate(doc) -> dict:
	"""Make the next version of the dossier PDF for a released mandate and store it. Returns the version and file."""
	from sellos.inventory.mandates import is_released

	if not is_released(doc):
		frappe.throw(_("The Dossier is released only when the mandate is signed."), frappe.PermissionError)
	version = (doc.dossier_version or 0) + 1
	content = build(view(doc, version))
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"dossier-{doc.name}-v{version}.pdf",
			"content": content,
			"is_private": 1,
			"attached_to_doctype": "Mandate",
			"attached_to_name": doc.name,
			"attached_to_field": DOSSIER_PDF_FIELD,
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	doc.dossier_pdf = file.file_url
	doc.dossier_version = version
	doc.dossier_generated_on = now_datetime()
	doc.dossier_generated_by = frappe.session.user
	doc.flags.ignore_permissions = (
		True  # the caller may write the mandate (checked); the PDF fields are the system's
	)
	doc.save()
	return {"version": version, "file": file.file_url}
