"""Onboard and approve channel partners (SOS-P7-01).

A Company Admin invites a channel partner firm by email. The invitation is SOS-P1-17's: it makes the
contact person's login with the Channel Partner role. The contact person then completes the firm's
details (phone, RERA agent registration number, PAN and the signed agreement), and the firm moves to
Pending approval. Only a Company Admin approves, suspends or reinstates a firm, and a suspension needs a
reason. Every move is logged with who made it and when. Nothing is deleted: a firm that leaves is Suspended.

* A partner whose firm is not Approved can register no lead and see no inventory (`partner_may_work`, which
  the lead permissions and, later, the inventory sharing of SOS-P7-03 use). The partner signs in to a page
  that says what state the firm is in. A login with no firm at all is an older partner login made before
  this task and is not held back; the invitation here always makes a firm.
* The PAN and the signed agreement are seen only by Company Admins. The agreement is a private file and
  a hook on File lets only a Company Admin open it, not even the partner who uploaded it.
* The firm's phone number is masked for every role but the Company Admin, as a lead's is.
* The partner code is the record's name, from a counter that only goes up, so it is never given twice.
"""

import base64
import binascii

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN
from sellos.crm.base import mask_phone
from sellos.sellos.doctype.channel_partner_firm.channel_partner_firm import (
	APPROVED,
	INVITED,
	PENDING,
	SUSPENDED,
)

FIRM = "Channel Partner Firm"
AGREEMENT_TYPES = (".pdf", ".png", ".jpg", ".jpeg")
AGREEMENT_LIMIT = 5 * 1024 * 1024
# What the contact person may fill in. The status and the code are never in this list.
PARTNER_FIELDS = ("firm_name", "contact_person", "phone", "rera_number", "pan")
ADMIN_FIELDS = (*PARTNER_FIELDS, "email")


# --- Who the partner works for --------------------------------------------------------------------


def firm_of(user=None) -> str | None:
	"""The name (partner code) of the firm whose contact login this is."""
	return frappe.db.get_value(FIRM, {"contact_user": user or frappe.session.user}, "name")


def partner_status(user=None) -> str | None:
	return frappe.db.get_value(FIRM, {"contact_user": user or frappe.session.user}, "status")


def partner_may_work(user=None) -> bool:
	"""False for a partner whose firm is not Approved: no lead can be registered or seen and no inventory
	is shown. A login with no firm is not held back (see the module note)."""
	status = partner_status(user)
	return status is None or status == APPROVED


def is_pure_partner(roles) -> bool:
	roles = set(roles)
	return CHANNEL_PARTNER in roles and not roles & {AGENT, COMPANY_ADMIN, "System Manager"}


def blocks_partner(user, roles) -> bool:
	"""True for a user whose only way in is a Channel Partner login on a firm that is not Approved."""
	return is_pure_partner(roles) and not partner_may_work(user)


# --- What each side sees --------------------------------------------------------------------------


def _log(doc) -> list[dict]:
	people = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	return [
		{
			"changed_on": row.changed_on,
			"changed_by": row.changed_by,
			"changed_by_name": people.get(row.changed_by, row.changed_by),
			"from_status": row.from_status,
			"to_status": row.to_status,
			"reason": row.reason or "",
		}
		for row in doc.status_log
	]


def _admin_view(doc) -> dict:
	"""Everything about a firm, for a Company Admin."""
	return {
		"name": doc.name,
		"partner_code": doc.partner_code,
		"firm_name": doc.firm_name,
		"status": doc.status,
		"status_reason": doc.status_reason or "",
		"contact_user": doc.contact_user,
		"contact_person": doc.contact_person,
		"email": doc.email,
		"phone": doc.phone or "",
		"rera_number": doc.rera_number or "",
		"pan": doc.pan or "",
		"agreement": doc.agreement or "",
		"missing": doc.missing_details(),
		"log": _log(doc),
	}


def _partner_view(doc) -> dict:
	"""What the contact person sees of their own firm: the phone masked, and the PAN and agreement only as
	whether they were given."""
	return {
		"name": doc.name,
		"partner_code": doc.partner_code,
		"firm_name": doc.firm_name,
		"status": doc.status,
		"status_reason": (doc.status_reason or "") if doc.status == SUSPENDED else "",
		"contact_person": doc.contact_person,
		"email": doc.email,
		"phone_masked": mask_phone(doc.phone),
		"rera_number": doc.rera_number or "",
		"has_pan": bool(doc.pan),
		"has_agreement": bool(doc.agreement),
		"missing": doc.missing_details(),
		"can_edit": doc.status in (INVITED, PENDING),
		"can_work": doc.status == APPROVED,
	}


def _firm(name):
	if not name or not frappe.db.exists(FIRM, name):
		frappe.throw(_("There is no partner firm {0}.").format(name), frappe.DoesNotExistError)
	return frappe.get_doc(FIRM, name)


def _my_firm():
	name = firm_of()
	if not name:
		frappe.throw(_("Your login is not linked to a partner firm."), frappe.PermissionError)
	return frappe.get_doc(FIRM, name)


def _values(values) -> dict:
	return frappe.parse_json(values) if isinstance(values, str) else (values or {})


def _counts() -> dict:
	return {
		status: frappe.db.count(FIRM, {"status": status})
		for status in (INVITED, PENDING, APPROVED, SUSPENDED)
	}


def _state() -> dict:
	names = frappe.get_all(FIRM, pluck="name", order_by="creation desc")
	return {"firms": [_admin_view(frappe.get_doc(FIRM, n)) for n in names], "counts": _counts()}


# --- The Company Admin ----------------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def list_partner_firms():
	"""Every firm with its details and status log, and how many are in each status."""
	return _state()


@sellos_api(COMPANY_ADMIN)
def invite_partner_firm(firm_name, contact_person, email, phone=""):
	"""Make the firm (status Invited) and invite its contact person with the Channel Partner role, through
	SOS-P1-17's invitation. The firm moves to Pending approval when the contact person completes it."""
	from sellos.access import users

	firm_name = " ".join(str(firm_name or "").split())
	contact_person = " ".join(str(contact_person or "").split())
	if not firm_name:
		frappe.throw(_("Enter the firm's name."))
	if not contact_person:
		frappe.throw(_("Enter the contact person's name."))
	if frappe.db.exists(FIRM, {"firm_name": firm_name}):
		frappe.throw(_("A firm called {0} already exists.").format(firm_name))
	email = str(email or "").strip().lower()
	invited = users.invite_user(email, contact_person, CHANNEL_PARTNER, mobile_no=phone)["invited"]
	doc = frappe.get_doc(
		{
			"doctype": FIRM,
			"firm_name": firm_name,
			"contact_user": email,
			"contact_person": contact_person,
			"email": email,
			"phone": phone,
		}
	)
	doc.insert()
	return {**_state(), "invited": invited, "name": doc.name, "email": email}


@sellos_api(COMPANY_ADMIN)
def update_partner_firm(name, values):
	"""A Company Admin corrects a firm's details (name, contact person, email, phone, RERA number, PAN)."""
	doc = _firm(name)
	values = _values(values)
	for field in ADMIN_FIELDS:
		if field in values:
			doc.set(field, values[field])
	doc.save()
	return {**_state(), "name": doc.name}


def _change(name, to, reason=""):
	doc = _firm(name)
	doc.check_permission("write")
	doc.change_status(to, reason)
	return {**_state(), "name": doc.name}


@sellos_api(COMPANY_ADMIN)
def approve_partner_firm(name):
	"""Approve a firm that is Pending approval. Only then may its partner work."""
	return _change(name, APPROVED)


@sellos_api(COMPANY_ADMIN)
def suspend_partner_firm(name, reason):
	"""Suspend a firm, with the reason. The partner signs in to a page that says so. Nothing is deleted."""
	return _change(name, SUSPENDED, reason)


@sellos_api(COMPANY_ADMIN)
def reinstate_partner_firm(name):
	"""Let a suspended firm work again."""
	return _change(name, APPROVED)


# --- The agreement (a private file) ---------------------------------------------------------------


_MAGIC = (b"%PDF", b"\x89PNG", b"\xff\xd8\xff")


def store_agreement(firm, filename, content) -> str:
	"""Save the signed agreement as a private file attached to the firm, and return its URL. `content` is the
	file's bytes."""
	filename = frappe.utils.cstr(filename).strip()
	if not filename.lower().endswith(AGREEMENT_TYPES):
		frappe.throw(_("The agreement must be a PDF, PNG or JPG file."))
	if not content or len(content) > AGREEMENT_LIMIT:
		frappe.throw(_("The agreement must be a file of up to 5 MB."))
	if not content.startswith(_MAGIC):
		frappe.throw(_("The agreement must be a PDF, PNG or JPG file."))
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"is_private": 1,
			"attached_to_doctype": FIRM,
			"attached_to_name": firm.name,
			"attached_to_field": "agreement",
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	firm.db_set("agreement", file.file_url)
	return file.file_url


def _decode(content_base64) -> bytes:
	text = str(content_base64 or "")
	if len(text) > AGREEMENT_LIMIT * 4 // 3 + 8:
		frappe.throw(_("The agreement must be a file of up to 5 MB."))
	try:
		return base64.b64decode(text, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The agreement could not be read. Choose the file again."))


@sellos_api(COMPANY_ADMIN)
def upload_agreement_for_firm(name, filename, content_base64):
	"""A Company Admin uploads a firm's signed agreement (the file's bytes as base64)."""
	doc = _firm(name)
	store_agreement(doc, filename, _decode(content_base64))
	return {**_state(), "name": doc.name}


def has_file_permission(doc, ptype=None, user=None, **kwargs):
	"""The signed agreement is opened by a Company Admin only: not the partner, not another role. Any other
	file is not this hook's business (it returns None, and Frappe's own rules decide)."""
	if doc.get("attached_to_doctype") != FIRM or doc.get("attached_to_field") != "agreement":
		return None
	user = user or frappe.session.user
	if user == "Administrator":
		return None
	return COMPANY_ADMIN in frappe.get_roles(user)


# --- The partner ----------------------------------------------------------------------------------


@sellos_api(CHANNEL_PARTNER)
def my_partner_firm():
	"""The signed in partner's own firm and what state it is in, or None for a login with no firm."""
	name = firm_of()
	return {"firm": _partner_view(frappe.get_doc(FIRM, name)) if name else None}


@sellos_api(CHANNEL_PARTNER)
def submit_partner_details(values):
	"""The contact person completes the firm's details. When all are given (and the agreement is uploaded)
	an invited firm moves to Pending approval. Once approved or suspended the details are the company's."""
	doc = _my_firm()
	if doc.status not in (INVITED, PENDING):
		frappe.throw(
			_("Your firm's details can not be changed now. Ask the company to change them."),
			frappe.PermissionError,
		)
	values = _values(values)
	for field in PARTNER_FIELDS:
		if field in values:
			doc.set(field, values[field])
	doc.flags.ignore_permissions = True
	doc.save()
	if doc.status == INVITED and not doc.missing_details():
		doc.change_status(PENDING)
	return {"firm": _partner_view(doc)}


@sellos_api(CHANNEL_PARTNER)
def upload_my_agreement(filename, content_base64):
	"""The contact person uploads the signed agreement (the file's bytes as base64)."""
	doc = _my_firm()
	if doc.status not in (INVITED, PENDING):
		frappe.throw(_("Your firm's details can not be changed now."), frappe.PermissionError)
	store_agreement(doc, filename, _decode(content_base64))
	doc.reload()
	if doc.status == INVITED and not doc.missing_details():
		doc.change_status(PENDING)
	return {"firm": _partner_view(doc)}


# --- Who may read a firm record -------------------------------------------------------------------


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	roles = frappe.get_roles(user)
	if COMPANY_ADMIN in roles or "System Manager" in roles:
		return ""
	if CHANNEL_PARTNER in roles:
		return f"`tab{FIRM}`.`contact_user` = {frappe.db.escape(user)}"
	return "1=0"


def has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	if COMPANY_ADMIN in roles or "System Manager" in roles:
		return True
	if CHANNEL_PARTNER in roles:
		return (ptype or "read") in ("read", "select") and doc.get("contact_user") == user
	return False
