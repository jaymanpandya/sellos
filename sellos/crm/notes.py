"""Notes on a lead, a seller and a mandate (SOS-LOOP, Leads and Sales round).

A note has a type from the company's managed list (Call, Site visit, Owner requirement, Price discussion, Legal
and title, Inspection, Photos, Document, Follow up, Other), its text, optional attachments, its author and a time.
The type Other asks for a short custom label. A note belongs to a lead; a note about a mandate also names the
mandate. Seller pages show the notes of the seller lead, so the seller and the mandate are reached the same way.

Who sees and changes what (docs/permissions.md):

* A Company Admin, an Agent and a Sales Manager may call these methods, and each call is judged on the record:
  a note is read by whoever may read its lead (and, if it is about a mandate, the mandate), and written by whoever
  may write the lead. A Client, a Channel Partner and the Platform Admin hold no note method: notes are the
  company's internal working notes, and showing them to a partner would show more than the lead page does.
* Only the author and a Company Admin edit or remove a note.
* Nothing is deleted. A removed note is hidden, with who removed it and when, and the change is also kept in the
  version history of the note (the DocType is change tracked), so a removal can always be traced.

Attachments are private files of up to 10 MB (up to 5 a note). Only images (PNG, JPG, WebP), PDF, DOCX, XLSX,
TXT and CSV are accepted, and the file's first bytes must agree with its name. A DOCX or XLSX that holds macros,
an OLE or old Office file, SVG, HTML, scripts and executables are refused. No file is ever run or rendered by
the server. There is no virus scanner on the server: the type check and the macro refusal are the protection.
"""

import base64
import binascii
import re
import zipfile
from io import BytesIO

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.inventory.base import squash

ROLES = (COMPANY_ADMIN, AGENT, SALES_MANAGER)
DEFAULT_TYPES = (
	"Call",
	"Site visit",
	"Owner requirement",
	"Price discussion",
	"Legal and title",
	"Inspection",
	"Photos",
	"Document",
	"Follow up",
	"Other",
)
OTHER = "Other"
CUSTOM_LABEL_MAX = 40
BODY_MAX = 5000
FILE_LIMIT = 10 * 1024 * 1024
FILES_PER_NOTE = 5
LIST_LIMIT = 200

IMAGE_TYPES = {".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".webp": b"RIFF"}
DOC_TYPES = (".pdf", ".docx", ".xlsx", ".txt", ".csv")
ALLOWED = (*IMAGE_TYPES, *DOC_TYPES)
ATTACH_FIELD = "attachments"


def _flag(value) -> bool:
	return str(value).lower() in ("1", "true", "yes")


def _list(value) -> list:
	return frappe.parse_json(value) if isinstance(value, str) else (value or [])


# --- The managed list of types ---------------------------------------------------------------------


def ensure_note_types():
	"""Make the ten starting types once, when the company has none. Safe to run again."""
	if frappe.db.count("Note Type"):
		return
	for order, label in enumerate(DEFAULT_TYPES, start=1):
		frappe.get_doc(
			{
				"doctype": "Note Type",
				"label": label,
				"is_other": int(label == OTHER),
				"enabled": 1,
				"sort_order": order,
			}
		).insert(ignore_permissions=True)


def _type_row(t) -> dict:
	return {"name": t.name, "label": t.label, "is_other": int(t.is_other), "enabled": int(t.enabled)}


def _types(only_shown=True) -> list[dict]:
	ensure_note_types()
	filters = {"enabled": 1} if only_shown else {}
	rows = frappe.get_all(
		"Note Type",
		filters=filters,
		fields=["name", "label", "is_other", "enabled"],
		order_by="sort_order asc, creation asc",
		ignore_permissions=True,
	)
	return [_type_row(r) for r in rows]


@sellos_api(*ROLES)
def note_types():
	"""The types a note can be given (the ones the company shows), in order."""
	return {"types": _types()}


@sellos_api(COMPANY_ADMIN)
def note_type_settings():
	"""Every type, shown or hidden, for the company's settings."""
	return {"types": _types(only_shown=False)}


@sellos_api(COMPANY_ADMIN)
def save_note_type(label, name=None, enabled=1):
	"""Add a type, or rename or hide one. The Other type can be renamed but never hidden, and no type is deleted."""
	label = squash(label)
	if not label or len(label) > 40:
		frappe.throw(_("Give the type a name of up to 40 characters."))
	ensure_note_types()
	taken = frappe.get_all("Note Type", fields=["name", "label"], ignore_permissions=True)
	if any(t.label.lower() == label.lower() and t.name != name for t in taken):
		frappe.throw(_("There is already a note type called {0}.").format(label))
	if name:
		doc = frappe.get_doc("Note Type", name)
		doc.label = label
		doc.enabled = int(_flag(enabled))
		if doc.is_other and not doc.enabled:
			frappe.throw(_("The Other type can not be hidden."))
	else:
		top = frappe.get_all("Note Type", fields=["sort_order"], order_by="sort_order desc", limit=1)
		last = top[0].sort_order if top else 0
		doc = frappe.get_doc(
			{
				"doctype": "Note Type",
				"label": label,
				"enabled": int(_flag(enabled)),
				"sort_order": cint(last) + 1,
			}
		)
	doc.save() if name else doc.insert()
	return {"name": doc.name, "types": _types(only_shown=False)}


# --- Attachments ------------------------------------------------------------------------------------


def _safe_name(filename) -> str:
	name = re.sub(r"[^A-Za-z0-9._ -]", "_", str(filename or "").replace("\\", "/").rsplit("/", 1)[-1])
	return squash(name)[:100] or "file"


def check_attachment(filename, content: bytes) -> str:
	"""Refuse a file that is not an allowed type, that is too big, or whose bytes do not match its name. Returns
	'Image' or 'Document'."""
	name = _safe_name(filename)
	ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
	if ext not in ALLOWED or not content:
		frappe.throw(_("Attach a PNG, JPG, WebP, PDF, DOCX, XLSX, TXT or CSV file."))
	if len(content) > FILE_LIMIT:
		frappe.throw(_("A file can be up to {0} MB.").format(FILE_LIMIT // (1024 * 1024)))
	if ext in IMAGE_TYPES:
		if not content.startswith(IMAGE_TYPES[ext]) or (ext == ".webp" and content[8:12] != b"WEBP"):
			frappe.throw(_("{0} is not a real image file.").format(name))
		return "Image"
	if ext == ".pdf":
		if not content.startswith(b"%PDF"):
			frappe.throw(_("{0} is not a real PDF file.").format(name))
	elif ext in (".docx", ".xlsx"):
		_check_office(name, content)
	else:
		try:
			text = content.decode("utf-8")
		except UnicodeDecodeError:
			frappe.throw(_("{0} is not a plain text file.").format(name))
		if "\x00" in text:
			frappe.throw(_("{0} is not a plain text file.").format(name))
	return "Document"


def _check_office(name, content):
	if not content.startswith(b"PK"):
		frappe.throw(_("{0} is not a real Office file.").format(name))
	try:
		with zipfile.ZipFile(BytesIO(content)) as z:
			names = [n.lower() for n in z.namelist()]
			if z.testzip() is not None:
				raise zipfile.BadZipFile
	except zipfile.BadZipFile:
		frappe.throw(_("{0} is not a real Office file.").format(name))
	if any("vbaproject" in n or n.endswith((".exe", ".dll", ".js", ".vbs", ".bat")) for n in names):
		frappe.throw(_("{0} holds macros or programs and is not accepted.").format(name))


def _decode(content_base64) -> bytes:
	text = str(content_base64 or "")
	if len(text) > FILE_LIMIT * 4 // 3 + 8:
		frappe.throw(_("A file can be up to {0} MB.").format(FILE_LIMIT // (1024 * 1024)))
	try:
		return base64.b64decode(text, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The file could not be read. Choose it again."))


def _checked(files, already=0) -> list:
	"""Check every file (type, size, bytes, count) before anything is written: [(name, content, kind)]."""
	files = _list(files)
	if already + len(files) > FILES_PER_NOTE:
		frappe.throw(_("A note holds up to {0} files.").format(FILES_PER_NOTE))
	checked = []
	for f in files:
		content = _decode(f.get("content_base64"))
		checked.append((_safe_name(f.get("filename")), content, check_attachment(f.get("filename"), content)))
	return checked


def _attach(note, checked) -> None:
	"""Store the checked files as private files of the note."""
	for filename, content, kind in checked:
		size = len(content)
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename,
				"content": content,
				"is_private": 1,
				"attached_to_doctype": "Record Note",
				"attached_to_name": note.name,
				"attached_to_field": ATTACH_FIELD,
			}
		)
		file.flags.ignore_permissions = True
		file.insert()
		note.append("attachments", {"file": file.file_url, "file_name": filename, "kind": kind, "size": size})


# --- Who may do what --------------------------------------------------------------------------------


def _has_note_role(user) -> bool:
	return user == "Administrator" or bool(set(frappe.get_roles(user)) & set(ROLES))


def get_permission_query_conditions(user=None, doctype="Record Note"):
	"""A list of notes is limited to the notes of leads the user may see, and to the note roles."""
	from sellos.access import lead_permissions as lp

	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	if not _has_note_role(user):
		return "1=0"
	return lp.get_child_query_conditions(user, doctype)


def has_permission(doc, ptype=None, user=None, **kwargs):
	"""Read: who may read the lead (and the mandate, for a mandate's note). Create: who may write the lead (and the
	mandate). Write: the author and a Company Admin. Nothing is deleted."""
	from sellos.access import lead_permissions as lp

	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if not _has_note_role(user):
		return False
	ptype = ptype or "read"
	if ptype == "delete":
		return False
	if not lp.has_child_permission(doc, "write" if ptype in ("create", "write") else "read", user):
		return False
	if doc.get("mandate") and not frappe.has_permission(
		"Mandate", "write" if ptype in ("create", "write") else "read", doc=doc.get("mandate"), user=user
	):
		return False
	if ptype == "write":
		return doc.get("owner") == user or COMPANY_ADMIN in frappe.get_roles(user)
	return True


def has_file_permission(doc, ptype=None, user=None, **kwargs):
	"""A note's file is opened by whoever may read the note. Any other file is not this hook's business."""
	if doc.get("attached_to_doctype") != "Record Note":
		return None
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	name = doc.get("attached_to_name")
	return bool(
		name
		and frappe.db.exists("Record Note", name)
		and frappe.has_permission("Record Note", "read", doc=name, user=user)
	)


def _note(name, write=False):
	if not name or not frappe.db.exists("Record Note", name):
		frappe.throw(_("There is no note {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Record Note", name)
	doc.check_permission("write" if write else "read")
	if write and doc.removed:
		frappe.throw(_("A removed note can not be changed."))
	return doc


# --- The calls ---------------------------------------------------------------------------------------


def _row(doc, people, types) -> dict:
	t = types.get(doc.note_type, {})
	label = doc.custom_label if t.get("is_other") and doc.custom_label else t.get("label", doc.note_type)
	return {
		"name": doc.name,
		"lead": doc.lead,
		"mandate": doc.mandate or "",
		"note_type": doc.note_type,
		"type_label": label,
		"is_other": int(bool(t.get("is_other"))),
		"custom_label": doc.custom_label or "",
		"body": doc.body or "",
		"author": doc.owner,
		"author_name": people.get(doc.owner, doc.owner),
		"created": str(doc.creation),
		"edited": int(str(doc.modified) != str(doc.creation)),
		"attachments": [
			{"file": a.file, "file_name": a.file_name, "kind": a.kind, "size": a.size}
			for a in doc.attachments
		],
		"can_edit": int(doc.owner == frappe.session.user or COMPANY_ADMIN in frappe.get_roles()),
	}


def notes_for(lead=None, mandate=None, note_type=None) -> list[dict]:
	"""The notes of a lead (all) or of a mandate, newest first, that the caller may read."""
	ensure_note_types()
	filters = {"removed": 0}
	if mandate:
		filters["mandate"] = mandate
	else:
		filters["lead"] = lead
	if note_type:
		filters["note_type"] = note_type
	names = frappe.get_list(
		"Record Note", filters=filters, pluck="name", order_by="creation desc", limit_page_length=LIST_LIMIT
	)
	people = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	types = {t["name"]: t for t in _types(only_shown=False)}
	rows = []
	for n in names:
		doc = frappe.get_doc("Record Note", n)
		if doc.has_permission("read"):
			rows.append(_row(doc, people, types))
	return rows


def _target(lead, mandate):
	if mandate:
		if not frappe.db.exists("Mandate", mandate):
			frappe.throw(_("There is no mandate {0}.").format(mandate), frappe.DoesNotExistError)
		lead = frappe.db.get_value("Mandate", mandate, "lead")
		frappe.get_doc("Mandate", mandate).check_permission("read")
	if not lead or not frappe.db.exists("Lead", lead):
		frappe.throw(_("There is no lead {0}.").format(lead), frappe.DoesNotExistError)
	frappe.get_doc("Lead", lead).check_permission("read")
	return lead, mandate or None


@sellos_api(*ROLES)
def list_notes(lead=None, mandate=None, note_type=None):
	"""The notes of a lead or a mandate the caller may read, newest first, optionally of one type."""
	lead, mandate = _target(lead, mandate)
	return {"notes": notes_for(lead, mandate, note_type), "types": _types()}


def _apply(doc, note_type, custom_label, body):
	if not note_type or not frappe.db.exists("Note Type", note_type):
		frappe.throw(_("Choose the type of the note."))
	t = frappe.db.get_value("Note Type", note_type, ["enabled", "is_other"], as_dict=True)
	if not t.enabled and doc.note_type != note_type:
		frappe.throw(_("That note type is hidden. Choose another."))
	label = squash(custom_label)
	if t.is_other:
		if not label:
			frappe.throw(_("Give the note a short label, because its type is Other."))
		if len(label) > CUSTOM_LABEL_MAX:
			frappe.throw(_("The label is up to {0} characters.").format(CUSTOM_LABEL_MAX))
	doc.note_type = note_type
	doc.custom_label = label if t.is_other else None
	body = str(body or "").strip()
	if len(body) > BODY_MAX:
		frappe.throw(_("A note is up to {0} characters.").format(BODY_MAX))
	doc.body = body


@sellos_api(*ROLES)
def add_note(note_type, body="", lead=None, mandate=None, custom_label="", files=None):
	"""Add a note to a lead (a seller is a lead) or to a mandate, with up to five attachments. Judged on the record:
	the caller must be able to write the lead (and the mandate)."""
	lead, mandate = _target(lead, mandate)
	frappe.get_doc("Lead", lead).check_permission("write")
	if mandate:
		frappe.get_doc("Mandate", mandate).check_permission("write")
	doc = frappe.get_doc({"doctype": "Record Note", "lead": lead, "mandate": mandate})
	_apply(doc, note_type, custom_label, body)
	checked = _checked(files)
	if not doc.body and not checked:
		frappe.throw(_("Write the note or attach a file."))
	doc.flags.attachments_pending = bool(checked)
	doc.insert()
	if checked:
		_attach(doc, checked)
		doc.save()
	return {"name": doc.name, "notes": notes_for(lead, mandate)}


@sellos_api(*ROLES)
def update_note(name, note_type, body="", custom_label="", files=None):
	"""Change a note's type, label or text, or add files. Only the author or a Company Admin."""
	doc = _note(name, write=True)
	_apply(doc, note_type, custom_label, body)
	checked = _checked(files, already=len(doc.attachments))
	_attach(doc, checked)
	if not doc.body and not doc.attachments:
		frappe.throw(_("Write the note or attach a file."))
	doc.save()
	return {"name": doc.name, "notes": notes_for(doc.lead, doc.mandate or None)}


@sellos_api(*ROLES)
def delete_note(name):
	"""Remove a note: it is hidden, never deleted, and who removed it and when is kept. Only the author or a Company
	Admin."""
	doc = _note(name, write=True)
	doc.removed = 1
	doc.removed_on = now_datetime()
	doc.removed_by = frappe.session.user
	doc.save(ignore_version=False)  # the removal is always kept in the version history
	return {"name": doc.name, "notes": notes_for(doc.lead, doc.mandate or None)}
