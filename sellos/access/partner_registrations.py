"""A channel partner registers a buyer, and the registration is protected in the partner's name (SOS-P7-02).

`register_buyer` is the one method by which a partner of an Approved firm (SOS-P7-01) registers a buyer.
SOS-P5-06's registration screen calls it and builds no second one.

* The phone and email go through SOS-P1-16's `find_matches`. A buyer who is already a client makes no
  second lead, and the partner is told only NOT_ACCEPTED: never who registered the buyer, their name,
  their agent or their stage. A refused try counts toward the hourly limit, so the limit also stops a
  partner from probing the company's buyers one number at a time.
* A new buyer makes a Client, a Lead (source Channel partner, the firm on `Lead.partner`, the first
  stage of the buyer pipeline) and a Partner Registration in status Registered.
* The registration keeps the consent wording that was shown. When the partner confirms the buyer agreed
  a Consent Record is made through SOS-P1-08, otherwise the lead's consent status stays Unknown with its
  warning. Consent never blocks anything.
* A Company Admin approves or rejects. An approved registration is protected for the company setting
  "Partner protection days", counted from the approval. Protection decides who is owed commission and
  never blocks a call, a message or an agent's work. While it lasts only a Company Admin changes the
  lead's partner, and the change is logged.
* Visited (a Site Visit marked Done), Booked (`mark_booked`, called by SOS-P7-10) and Expired
  (`expire_registrations`, which the tests call with a fixed clock) follow the lead.
* A partner sees only their own registrations, with the phone masked, and changes nothing afterwards.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, get_url, now_datetime, validate_email_address

from sellos.access.partner_firms import FIRM, firm_of, is_pure_partner, partner_status
from sellos.access.registry import sellos_api
from sellos.access.roles import CHANNEL_PARTNER, COMPANY_ADMIN
from sellos.crm import consent
from sellos.crm.base import mask_phone
from sellos.crm.duplicates import find_matches, normalise_email, normalise_phone
from sellos.crm.lead_sources import CHANNEL_PARTNER as SOURCE
from sellos.sellos.doctype.channel_partner_firm.channel_partner_firm import APPROVED as FIRM_APPROVED
from sellos.sellos.doctype.partner_registration.partner_registration import (
	APPROVED,
	BOOKED,
	EXPIRED,
	LIVE,
	REGISTERED,
	REJECTED,
	STATUSES,
	VISITED,
	raw_setting,
)

REG = "Partner Registration"
ATTEMPT = "Partner Registration Attempt"
SETTINGS = "SellOS Settings"

# The only thing a partner is told about a buyer the company already has (SOS-P7-02).
NOT_ACCEPTED = "Not accepted: this buyer is already registered with the company."

DEFAULT_LIMIT = 20
# The default of the company setting "Consent wording" (Jayman, 24 November 2026, SOS-N22). {company} is
# replaced with the company's display name wherever the wording is shown (render_wording).
DEFAULT_WORDING = (
	"I agree that {company} and its agents may contact me about my enquiry by phone, SMS, WhatsApp "
	"and email. I can ask them to stop at any time."
)
COMPANY_PLACEHOLDER = "{company}"
FALLBACK_COMPANY = "the company"


# --- The company settings ---------------------------------------------------------------------------


def lead_limit() -> int:
	"""Leads one partner may register in an hour (company setting "Partner lead limit", default 20)."""
	value = raw_setting("partner_lead_limit")
	return DEFAULT_LIMIT if value is None else max(cint(value), 0)


def company_display_name() -> str:
	"""The company's display name (company setting "Company name"), or "the company" while it is empty."""
	return (frappe.db.get_single_value(SETTINGS, "company_name") or "").strip() or FALLBACK_COMPANY


def render_wording(text: str, company: str | None = None) -> str:
	"""Replace {company} in a consent wording with the company's display name (SOS-N22). Plain text
	replacement, so no other brace in the wording is touched and the display name is never formatted."""
	return (text or "").replace(COMPANY_PLACEHOLDER, company or company_display_name())


def raw_consent_wording() -> str:
	"""The wording as the Company Admin saved it, {company} still in it (the settings screen edits this)."""
	return (frappe.db.get_single_value(SETTINGS, "consent_wording") or "").strip() or DEFAULT_WORDING


def consent_wording() -> str:
	"""The wording to show: the setting, or the default, with {company} replaced by the display name."""
	return render_wording(raw_consent_wording())


def protection_days() -> int:
	from sellos.sellos.doctype.partner_registration.partner_registration import protection_days as days

	return days()


@sellos_api(COMPANY_ADMIN)
def get_partner_settings():
	"""The three company settings of the partner programme."""
	return {
		"partner_lead_limit": lead_limit(),
		"partner_protection_days": protection_days(),
		"consent_wording": raw_consent_wording(),
	}


@sellos_api(COMPANY_ADMIN)
def save_partner_settings(partner_lead_limit=None, partner_protection_days=None, consent_wording=None):
	"""Change the partner lead limit (per partner per hour), the protection days and the consent wording."""
	for field, value, label in (
		("partner_lead_limit", partner_lead_limit, _("Partner lead limit")),
		("partner_protection_days", partner_protection_days, _("Partner protection days")),
	):
		if value in (None, ""):
			continue
		if cint(value) < 1:
			frappe.throw(_("{0} must be at least 1.").format(label))
		frappe.db.set_single_value(SETTINGS, field, cint(value))
	if consent_wording is not None:
		frappe.db.set_single_value(SETTINGS, "consent_wording", str(consent_wording).strip())
	return get_partner_settings()


# --- Who may register ---------------------------------------------------------------------------------


def _approved_partner() -> str:
	"""The signed in partner's firm, when it is Approved. Anyone else is refused with a clear message."""
	name = firm_of()
	if not name or partner_status() != FIRM_APPROVED:
		frappe.throw(_("Only a partner of an approved firm can register a buyer."), frappe.PermissionError)
	return name


def _attempts_in_the_last_hour(user, on) -> int:
	return frappe.db.count(ATTEMPT, {"partner_user": user, "attempted_on": [">", add_to_date(on, hours=-1)]})


def _check_rate(user, on) -> int:
	"""Refuse the try past the limit. Returns how many registrations the partner has left this hour."""
	limit = lead_limit()
	used = _attempts_in_the_last_hour(user, on)
	if used >= limit:
		frappe.throw(
			_(
				"You have registered {0} buyers in the last hour, which is the most the company allows. Try again later."
			).format(limit),
			frappe.TooManyRequestsError,
		)
	return limit - used


def _note_attempt(user, firm, result, on):
	frappe.get_doc(
		{
			"doctype": ATTEMPT,
			"partner_user": user,
			"partner_firm": firm,
			"attempted_on": on,
			"result": result,
		}
	).insert(ignore_permissions=True)


# --- Registering a buyer --------------------------------------------------------------------------------


def _clean(value) -> str:
	return " ".join(str(value or "").split())


@sellos_api(CHANNEL_PARTNER)
def partner_registration_form():
	"""What the registration screen shows: the consent wording, and how many more buyers this partner may
	register this hour."""
	firm = _approved_partner()
	now = now_datetime()
	return {
		"firm_name": frappe.db.get_value(FIRM, firm, "firm_name"),
		"consent_wording": consent_wording(),
		"limit": lead_limit(),
		"remaining": max(lead_limit() - _attempts_in_the_last_hour(frappe.session.user, now), 0),
	}


@sellos_api(CHANNEL_PARTNER)
def register_buyer(buyer_name, phone, project_of_interest="", note="", buyer_agreed=0, email=""):
	"""Register a buyer for the signed in partner. Returns {"accepted": True, "registration": ...}, or for a
	buyer the company already has {"accepted": False, "message": NOT_ACCEPTED} and nothing else."""
	return register(buyer_name, phone, project_of_interest, note, buyer_agreed, email)


def register(buyer_name, phone, project_of_interest="", note="", buyer_agreed=0, email="", on=None):
	"""The body of `register_buyer`. `on` is the clock, for tests."""
	user = frappe.session.user
	firm = _approved_partner()
	on = on or now_datetime()
	remaining = _check_rate(user, on)

	buyer_name = _clean(buyer_name)
	if not buyer_name:
		frappe.throw(_("Enter the buyer's name."))
	key = normalise_phone(phone)
	if not key:
		frappe.throw(_("Enter the buyer's phone number with its country code, or as ten digits."))
	email = normalise_email(email)
	if email and not validate_email_address(email):
		frappe.throw(_("Enter a valid email address, or leave it empty."))

	if find_matches(phone=key, email=email):
		_note_attempt(user, firm, "Not accepted", on)
		return {"accepted": False, "message": NOT_ACCEPTED}

	project = _clean(project_of_interest)
	note = str(note or "").strip()
	client = frappe.get_doc(
		{
			"doctype": "Client",
			"client_name": buyer_name,
			"client_type": "Buyer",
			"phone": key,
			"email": email or None,
		}
	).insert(ignore_permissions=True)
	details = "\n".join(
		part for part in (note, f"{_('Project of interest')}: {project}" if project else "") if part
	)
	lead = frappe.get_doc(
		{"doctype": "Lead", "client": client.name, "source": SOURCE, "partner": firm, "notes": details}
	)
	lead.flags.partner_registration = True
	lead.insert(ignore_permissions=True)
	agreed = 1 if cint(buyer_agreed) else 0
	reg = frappe.get_doc(
		{
			"doctype": REG,
			"buyer_name": buyer_name,
			"partner_firm": firm,
			"partner_user": user,
			"lead": lead.name,
			"client": client.name,
			"project_of_interest": project,
			"note": note,
			"phone_masked": mask_phone(key),
			"consent_wording": consent_wording(),
			"buyer_agreed": agreed,
			"registered_on": on,
		}
	).insert(ignore_permissions=True)
	if agreed:
		# SOS-P1-08: the partner's confirmation is the basis, and the registration is the evidence.
		frappe.get_doc(
			{
				"doctype": "Consent Record",
				"lead": lead.name,
				"basis": "Consent",
				"evidence_link": f"{get_url()}/sellos/partner/registrations/{reg.name}",
				"recorded_on": on,
			}
		).insert(ignore_permissions=True)
	_note_attempt(user, firm, "Registered", on)
	return {
		"accepted": True,
		"remaining": remaining - 1,
		"registration": _partner_view(frappe.get_doc(REG, reg.name)),
	}


# --- What each side sees ----------------------------------------------------------------------------------


def _consent_of(lead) -> dict:
	view = consent.consent_view(lead)
	return {"status": view["status"], "warning": view["warning"], "message": view["message"]}


def is_protected(lead, on=None) -> bool:
	"""True while the lead's registration decides who is owed commission: Approved or Visited and inside
	the window, or Booked."""
	row = frappe.db.get_value(
		REG, {"lead": lead}, ["status", "protected_until"], as_dict=True, order_by="creation desc"
	)
	if not row:
		return False
	if row.status == BOOKED:
		return True
	return (
		row.status in LIVE
		and bool(row.protected_until)
		and get_datetime(row.protected_until) > get_datetime(on or now_datetime())
	)


def _partner_view(doc) -> dict:
	"""What the partner sees of their own registration: the phone masked, and the moves without the
	company's internal notes."""
	return {
		"name": doc.name,
		"buyer_name": doc.buyer_name,
		"status": doc.status,
		"project_of_interest": doc.project_of_interest or "",
		"phone_masked": doc.phone_masked or "",
		"note": doc.note or "",
		"lead": doc.lead,
		"registered_on": doc.registered_on,
		"approved_on": doc.approved_on,
		"protected_until": doc.protected_until,
		"rejection_reason": (doc.rejection_reason or "") if doc.status == REJECTED else "",
		"consent": _consent_of(doc.lead),
		"log": [
			{"changed_on": row.changed_on, "from_status": row.from_status, "to_status": row.to_status}
			for row in doc.status_log
			if row.from_status != row.to_status
		],
	}


def _admin_view(doc) -> dict:
	phone = frappe.db.get_value("Client", doc.client, "phone") if doc.client else ""
	return {
		**{k: v for k, v in _partner_view(doc).items() if k != "log"},
		"phone": phone or "",
		"partner_firm": doc.partner_firm,
		"firm_name": frappe.db.get_value(FIRM, doc.partner_firm, "firm_name"),
		"partner_user": doc.partner_user,
		"buyer_agreed": bool(doc.buyer_agreed),
		"consent_wording": doc.consent_wording or "",
		"protected": is_protected(doc.lead),
		"decided_by": doc.decided_by,
		"log": [
			{
				"changed_on": row.changed_on,
				"changed_by": row.changed_by,
				"from_status": row.from_status,
				"to_status": row.to_status,
				"note": row.note or "",
			}
			for row in doc.status_log
		],
	}


def _counts() -> dict:
	return {status: frappe.db.count(REG, {"status": status}) for status in STATUSES}


@sellos_api(COMPANY_ADMIN)
def list_partner_registrations(status=None):
	"""Every registration with its log, newest first, and how many are in each status."""
	filters = {"status": status} if status in STATUSES else {}
	names = frappe.get_all(REG, filters=filters, pluck="name", order_by="creation desc")
	return {"registrations": [_admin_view(frappe.get_doc(REG, n)) for n in names], "counts": _counts()}


@sellos_api(CHANNEL_PARTNER)
def my_partner_registrations():
	"""The signed in partner's own registrations and where each one stands."""
	_approved_partner()
	names = frappe.get_list(
		REG, filters={"partner_user": frappe.session.user}, pluck="name", order_by="creation desc"
	)
	return {"registrations": [_partner_view(frappe.get_doc(REG, n)) for n in names]}


# --- The Company Admin decides ---------------------------------------------------------------------------


def _registration(name):
	if not name or not frappe.db.exists(REG, name):
		frappe.throw(_("There is no registration {0}.").format(name), frappe.DoesNotExistError)
	return frappe.get_doc(REG, name)


@sellos_api(COMPANY_ADMIN)
def approve_partner_registration(name):
	"""Approve a registration. It is protected in the partner's name from now for the Partner protection days."""
	doc = _registration(name)
	doc.change_status(APPROVED)
	return list_partner_registrations() | {"name": doc.name}


@sellos_api(COMPANY_ADMIN)
def reject_partner_registration(name, reason):
	"""Reject a registration, with the reason. The partner sees the reason."""
	doc = _registration(name)
	doc.change_status(REJECTED, reason)
	return list_partner_registrations() | {"name": doc.name}


@sellos_api(COMPANY_ADMIN)
def change_lead_partner(lead, partner_firm=None):
	"""Move a lead to another partner firm, or to none. Only a Company Admin does it, also while the
	registration is protected. The change is logged on the registration and as a comment on the lead."""
	if not frappe.db.exists("Lead", lead):
		frappe.throw(_("There is no lead {0}.").format(lead), frappe.DoesNotExistError)
	partner_firm = partner_firm or None
	if partner_firm and not frappe.db.exists(FIRM, partner_firm):
		frappe.throw(_("There is no partner firm {0}.").format(partner_firm), frappe.DoesNotExistError)
	doc = frappe.get_doc("Lead", lead)
	old = doc.partner
	if old == partner_firm:
		return {"lead": lead, "partner": old}
	doc.partner = partner_firm
	doc.flags.ignore_permissions = True
	doc.save()
	line = _("The lead's partner was changed from {0} to {1} by {2}.").format(
		old or _("none"), partner_firm or _("none"), frappe.session.user
	)
	doc.add_comment("Info", line)
	for name in frappe.get_all(REG, filters={"lead": lead}, pluck="name"):
		frappe.get_doc(REG, name).log_note(line)
	return {"lead": lead, "partner": partner_firm}


def check_partner_change(lead) -> None:
	"""Run when a lead is saved. The partner on a lead is set by the registration and changed by a Company
	Admin, and by nobody else, protected or not."""
	changed = bool(lead.partner) if lead.is_new() else lead.has_value_changed("partner")
	if not changed or lead.flags.partner_registration:
		return
	user = frappe.session.user
	if user == "Administrator" or COMPANY_ADMIN in frappe.get_roles(user):
		return
	frappe.throw(_("Only a Company Admin can change the partner of a lead."), frappe.PermissionError)


# --- What follows the lead ---------------------------------------------------------------------------------


def _live_registration(lead, status):
	name = frappe.db.get_value(REG, {"lead": lead, "status": status}, "name")
	return frappe.get_doc(REG, name) if name else None


def mark_visited(lead) -> bool:
	"""A Site Visit on the lead was marked Done: an Approved registration becomes Visited."""
	doc = _live_registration(lead, APPROVED)
	if not doc:
		return False
	doc.change_status(VISITED, _("A site visit was marked done."))
	return True


def on_site_visit_saved(visit, method=None) -> None:
	"""Site Visit on_update (SOS-P7-02)."""
	if visit.status == "Done" and visit.lead:
		mark_visited(visit.lead)


def mark_booked(lead) -> bool:
	"""A booking on the lead (SOS-P7-10 calls this): an Approved or Visited registration becomes Booked."""
	doc = _live_registration(lead, VISITED) or _live_registration(lead, APPROVED)
	if not doc:
		return False
	doc.change_status(BOOKED, _("The lead was booked."))
	return True


def expire_registrations(on=None) -> list[str]:
	"""Every Approved or Visited registration whose protection window has ended without a booking becomes
	Expired. `on` is the clock. Safe to run again. Scheduled hourly."""
	on = get_datetime(on or now_datetime())
	names = frappe.get_all(
		REG,
		filters={"status": ["in", list(LIVE)], "protected_until": ["<=", on]},
		pluck="name",
		order_by="protected_until asc",
	)
	for name in names:
		frappe.get_doc(REG, name).change_status(
			EXPIRED, _("The protection window ended without a booking."), on
		)
	return names


# --- Who may read a registration -----------------------------------------------------------------------------


def get_permission_query_conditions(user=None):
	from sellos.access.partner_firms import blocks_partner

	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	roles = frappe.get_roles(user)
	if COMPANY_ADMIN in roles or "System Manager" in roles:
		return ""
	if CHANNEL_PARTNER in roles and not blocks_partner(user, roles):
		return f"`tab{REG}`.`partner_user` = {frappe.db.escape(user)}"
	return "1=0"


def has_permission(doc, ptype=None, user=None, **kwargs):
	from sellos.access.partner_firms import blocks_partner

	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	if COMPANY_ADMIN in roles or "System Manager" in roles:
		return True
	if is_pure_partner(roles) and not blocks_partner(user, roles):
		return (ptype or "read") in ("read", "select") and doc.get("partner_user") == user
	return False
