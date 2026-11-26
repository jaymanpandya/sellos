"""Mandates and their Private Sale Dossier in the web app (SOS-P4-05).

A mandate is an owner's agreement that the company sells a property. It is Exclusive or Open, with a term and a
fee, and is a Draft until its signed document is uploaded. A Company Admin or an Agent records it for a seller
lead they may write, signs it, adds notes and files to its dossier and opens the dossier. A Sales Manager, a
Client, a Channel Partner and the Platform Admin hold no mandate method.

The Private Sale Dossier (Jayman, SOS-SETUP-34) is the files and notes attached to a mandate. It is released only
when the mandate is signed and not archived: until then `open_dossier` is refused, the overview shows no item of it
and no count, and its files can not be downloaded. Each opening is logged with who and when. A seller reaches the
Listed stage only with a signed mandate (SOS-P4-04's stage rule, built in sellos.crm.pipeline). Every call saves
through the Mandate DocType, so its checks and the lead permissions run on every call. Nothing is deleted.
"""

import base64
import binascii

import frappe
from frappe import _
from frappe.utils import now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.inventory.base import squash
from sellos.sellos.doctype.mandate.mandate import DRAFT, SIGNED, TYPES

ROLES = (COMPANY_ADMIN, AGENT)

# What a caller may set on a mandate. The status, the signature and the dossier are never in this list.
FIELDS = ("lead", "mandate_type", "start_date", "term_months", "fee_percent")

FILE_TYPES = (".pdf", ".png", ".jpg", ".jpeg")
FILE_LIMIT = 5 * 1024 * 1024
_MAGIC = (b"%PDF", b"\x89PNG", b"\xff\xd8\xff")
SIGNED_FIELD = "signed_document"
DOSSIER_FIELD = "dossier_file"
DOSSIER_PDF_FIELD = "dossier_pdf"  # SOS-LOOP: the branded PDF of the Dossier


def _values(values) -> dict:
	return frappe.parse_json(values) if isinstance(values, str) else (values or {})


def _flag(value) -> bool:
	return str(value).lower() in ("1", "true", "yes")


def is_released(doc) -> bool:
	"""The Dossier is released only for a signed mandate that is not archived."""
	return doc.status == SIGNED and not doc.archived


def _mandate(name, write=False):
	if not name or not frappe.db.exists("Mandate", name):
		frappe.throw(_("There is no mandate {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Mandate", name)
	doc.check_permission("write" if write else "read")
	if write and doc.archived:
		frappe.throw(_("An archived mandate can not be changed."))
	return doc


def _people() -> dict:
	return {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}


def _row(doc, people) -> dict:
	lead = frappe.db.get_value("Lead", doc.lead, ["lead_title", "client"], as_dict=True) or {}
	released = is_released(doc)
	return {
		"name": doc.name,
		"lead": doc.lead,
		"lead_title": lead.get("lead_title") or doc.lead,
		"client_name": frappe.db.get_value("Client", lead.get("client"), "client_name") or "",
		"mandate_type": doc.mandate_type,
		"start_date": str(doc.start_date or ""),
		"term_months": doc.term_months,
		"ends_on": str(doc.ends_on or ""),
		"fee_percent": doc.fee_percent,
		"status": doc.status,
		"signed_on": str(doc.signed_on or ""),
		"signed_by_name": people.get(doc.signed_by, doc.signed_by or ""),
		"has_signed_document": int(bool(doc.signed_document)),
		"signed_document": doc.signed_document or "",
		"archived": int(doc.archived or 0),
		# Nothing of the Dossier is shown before it is released, not even how many items it holds.
		"dossier_released": int(released),
		"dossier_count": len(doc.dossier) if released else None,
		# The branded PDF is part of the Dossier: nothing of it shows before the mandate is signed.
		"dossier_pdf": (
			{
				"version": doc.dossier_version,
				"file": doc.dossier_pdf,
				"generated_on": str(doc.dossier_generated_on or ""),
			}
			if released and doc.dossier_pdf
			else None
		),
		**signing_row(doc),
	}


AUDIT_FIELD = "audit_trail"  # SOS-LOOP: DocuSeal's audit trail of a signed mandate
SENT_FIELD = "mandate_document"  # SOS-LOOP: the document that went to the signers


def signing_row(doc) -> dict:
	"""Where electronic signing stands, for the list and the page (SOS-LOOP). The signed copy and the audit trail are
	links only once the mandate is signed."""
	signed = doc.status == SIGNED
	return {
		"signing_status": doc.signing_status or "Not sent",
		"signing_sent_on": str(doc.signing_sent_on or ""),
		"signing_completed_on": str(doc.signing_completed_on or ""),
		"signers": [
			{
				"role": s.role,
				"name": s.signer_name or "",
				"status": s.status,
				"sent_on": str(s.sent_on or ""),
				"viewed_on": str(s.viewed_on or ""),
				"completed_on": str(s.completed_on or ""),
			}
			for s in doc.signers
		],
		"signed_copy": doc.signed_document if signed and doc.signing_provider else "",
		"audit_trail": doc.audit_trail if signed else "",
	}


def _seller_leads() -> list[dict]:
	rows = frappe.get_list(
		"Lead",
		filters={"pipeline": "Seller", "archived": 0},
		fields=["name", "lead_title"],
		limit_page_length=500,
	)
	return [{"value": r.name, "label": r.lead_title or r.name} for r in rows]


def _overview(include_archived=False) -> dict:
	filters = {} if include_archived else {"archived": 0}
	people = _people()
	names = frappe.get_list("Mandate", filters=filters, pluck="name", order_by="creation desc")
	return {
		"mandates": [_row(frappe.get_doc("Mandate", n), people) for n in names],
		"sellers": _seller_leads(),
		"mandate_types": list(TYPES),
		"can_archive": COMPANY_ADMIN in frappe.get_roles(),
		"file_types": ", ".join(t[1:].upper() for t in FILE_TYPES),
		"file_limit_mb": FILE_LIMIT // (1024 * 1024),
	}


@sellos_api(*ROLES)
def mandate_overview(include_archived=0):
	"""The mandates of the seller leads the caller may see, and the sellers a mandate can be made for. The
	Dossier of a mandate that is not signed shows nothing, not even a count."""
	return _overview(_flag(include_archived))


STATUS_LIMIT = 200


@sellos_api(SALES_MANAGER)
def mandate_status(leads):
	"""A Sales Manager reads, for the seller leads of its own team, only the id and the status of each mandate
	(Draft or Signed). Nothing else is returned: no term, fee, document, Dossier or count. A lead the caller may
	not read is left out, and so is an archived mandate."""
	names = [str(n) for n in (frappe.parse_json(leads) if isinstance(leads, str) else leads or [])]
	names = list(dict.fromkeys(names))[:STATUS_LIMIT]
	readable = [
		n for n in names if frappe.db.exists("Lead", n) and frappe.has_permission("Lead", "read", doc=n)
	]
	if not readable:
		return {"mandates": []}
	rows = frappe.get_all(  # the caller's right is the lead permission checked above
		"Mandate",
		filters={"lead": ["in", readable], "archived": 0},
		fields=["name", "lead", "status"],
		order_by="creation desc",
		ignore_permissions=True,
	)
	return {"mandates": [{"name": r.name, "lead": r.lead, "status": r.status} for r in rows]}


@sellos_api(*ROLES)
def save_mandate(values, name=None):
	"""Make a mandate (a Draft, never signed by this call), or correct a Draft. A signed mandate keeps its terms."""
	values = _values(values)
	if name:
		doc = _mandate(name, write=True)
		for field in FIELDS:
			if field in values:
				doc.set(field, values[field])
		doc.save()
	else:
		data = {k: values[k] for k in FIELDS if k in values}
		doc = frappe.get_doc({"doctype": "Mandate", **data, "status": DRAFT})
		doc.insert()
	return {"name": doc.name, **_overview()}


# --- Files (private) ----------------------------------------------------------------------------


def _decode(content_base64) -> bytes:
	text = str(content_base64 or "")
	if len(text) > FILE_LIMIT * 4 // 3 + 8:
		frappe.throw(_("A file can be up to {0} MB.").format(FILE_LIMIT // (1024 * 1024)))
	try:
		return base64.b64decode(text, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The file could not be read. Choose it again."))


def check_file(filename, content: bytes):
	"""Refuse a file that is not a PDF, PNG or JPG of up to 5 MB: its name and its first bytes must agree."""
	name = frappe.utils.cstr(filename).strip().lower()
	if not name.endswith(FILE_TYPES) or not content or not content.startswith(_MAGIC):
		frappe.throw(_("The file must be a PDF, PNG or JPG file."))
	if len(content) > FILE_LIMIT:
		frappe.throw(_("A file can be up to {0} MB.").format(FILE_LIMIT // (1024 * 1024)))


def _store(doc, filename, content, field) -> str:
	"""Save the file as a private file attached to the mandate and return its URL."""
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": squash(filename)[:140],
			"content": content,
			"is_private": 1,
			"attached_to_doctype": "Mandate",
			"attached_to_name": doc.name,
			"attached_to_field": field,
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	return file.file_url


@sellos_api(*ROLES)
def sign_mandate(name, filename, content_base64):
	"""Sign a mandate by uploading its signed document (a PDF, PNG or JPG of up to 5 MB, as base64). The
	document is required: without it the mandate stays a Draft. Signing releases the Dossier."""
	doc = _mandate(name, write=True)
	if doc.status == SIGNED:
		frappe.throw(_("This mandate is already signed."))
	content = _decode(content_base64)
	check_file(filename, content)
	doc.sign(_store(doc, filename, content, SIGNED_FIELD))
	doc.save()
	return {"name": doc.name, **_overview()}


# --- The Private Sale Dossier -------------------------------------------------------------------


def _add_item(doc, row):
	doc.append("dossier", {**row, "added_by": frappe.session.user, "added_on": now_datetime()})
	doc.flags.ignore_permissions = (
		True  # the caller may write the mandate (checked); the table is above level 0
	)
	doc.save()


@sellos_api(*ROLES)
def add_dossier_note(name, title, note):
	"""Add a note to the dossier. It can be added before the mandate is signed, and stays hidden until then."""
	doc = _mandate(name, write=True)
	_add_item(doc, {"kind": "Note", "title": title, "note": note})
	return {"name": doc.name, **_overview()}


@sellos_api(*ROLES)
def add_dossier_file(name, title, filename, content_base64):
	"""Add a file (a PDF, PNG or JPG of up to 5 MB, as base64) to the dossier, as a private file. It stays hidden
	until the mandate is signed."""
	doc = _mandate(name, write=True)
	content = _decode(content_base64)
	check_file(filename, content)
	title = squash(title) or squash(str(filename).rsplit(".", 1)[0])
	_add_item(doc, {"kind": "File", "title": title, "file": _store(doc, filename, content, DOSSIER_FIELD)})
	return {"name": doc.name, **_overview()}


@sellos_api(*ROLES)
def open_dossier(name):
	"""Open the Private Sale Dossier: its notes and files, and who has viewed it. Refused unless the mandate is
	signed (and not archived). Each opening is logged with who and when."""
	doc = _mandate(name)
	if not is_released(doc):
		frappe.throw(_("The Dossier is released only when the mandate is signed."), frappe.PermissionError)
	doc.append("views", {"viewed_by": frappe.session.user, "viewed_on": now_datetime()})
	doc.flags.ignore_permissions = True  # a view is logged for a person who may only read
	doc.save()
	people = _people()
	return {
		"name": doc.name,
		"items": [
			{
				"kind": i.kind,
				"title": i.title,
				"note": i.note or "",
				"file": i.file or "",
				"added_by_name": people.get(i.added_by, i.added_by or ""),
				"added_on": str(i.added_on or ""),
			}
			for i in doc.dossier
		],
		"views": [
			{"viewed_by_name": people.get(v.viewed_by, v.viewed_by), "viewed_on": str(v.viewed_on)}
			for v in reversed(doc.views)
		],
	}


@sellos_api(*ROLES)
def generate_dossier_pdf(name):
	"""Make the next version of the Dossier as a branded PDF (the company's logo and colours, a cover page, the seller
	and property, the mandate and its signing status, the notes by type with their images, and page numbers) and keep
	it on the mandate. Refused unless the mandate is signed and not archived. Every version is kept."""
	from sellos.inventory import dossier_pdf

	doc = _mandate(name, write=True)
	dossier_pdf.generate(doc)
	return {"name": doc.name, **_overview()}


@sellos_api(COMPANY_ADMIN)
def set_mandate_archived(name, archived=1):
	"""Archive a mandate, or restore it. An archived mandate no longer counts as signed for the Listed stage and
	its Dossier is no longer released. Nothing is deleted."""
	doc = _mandate(name)
	doc.check_permission("write")
	doc.archived = 1 if _flag(archived) else 0
	doc.save()
	return {"name": doc.name, **_overview()}


def has_file_permission(doc, ptype=None, user=None, **kwargs):
	"""A mandate's files are opened only by who may read the mandate, and a dossier file only while the mandate is
	signed. Any other file is not this hook's business (it returns None). Called by
	sellos.access.file_permissions, which owns the File hook."""
	if doc.get("attached_to_doctype") != "Mandate" or doc.get("attached_to_field") not in (
		SIGNED_FIELD,
		DOSSIER_FIELD,
		DOSSIER_PDF_FIELD,
		AUDIT_FIELD,
		SENT_FIELD,
	):
		return None
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	mandate = frappe.db.get_value(
		"Mandate", doc.get("attached_to_name"), ["name", "status", "archived"], as_dict=True
	)
	if not mandate or not frappe.has_permission("Mandate", "read", doc=mandate.name, user=user):
		return False
	if doc.get("attached_to_field") in (DOSSIER_FIELD, DOSSIER_PDF_FIELD):
		return mandate.status == SIGNED and not mandate.archived
	return True
