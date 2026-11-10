"""Support access grants (P1.13).

The Platform Admin sees no company data by role (P1.06). A Company Admin may give one support user
read access for a chosen time, at most 4 hours. While the grant is active:

* `lead_permissions` lets that user read the CRM records, and nothing else: no write, create,
  delete or share.
* every request the user makes is written to the Support Access Log, with the user, the time, the
  method and the path (`log_support_request`, a `before_request` hook).

The end is checked on every use (`active_grant`), so access stops at expiry whether or not the
scheduler has run. The scheduler only marks the grant Expired and logs it (`expire_due_grants`).
Nothing here is deleted: grants and log lines are kept.
"""

import re

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN, PLATFORM_ADMIN
from sellos.sellos.doctype.support_grant.support_grant import MAX_MINUTES

GRANT = "Support Grant"
LOG = "Support Access Log"
PATH_LIMIT = 500
_RESOURCE_PATH = re.compile(r"^/api/resource/(?P<doctype>[^/]+)(?:/(?P<name>[^?]+))?$")


# --- Is a grant active ----------------------------------------------------------------------------


def grant_end(starts_at, expires_at):
	"""When a grant really ends: its expiry, and never later than 4 hours after it started."""
	return min(get_datetime(expires_at), add_to_date(get_datetime(starts_at), minutes=MAX_MINUTES))


def active_grant(user=None) -> str | None:
	"""The name of the user's grant that is active now, or None."""
	user = user or frappe.session.user
	if not user or user in ("Guest", "Administrator"):
		return None
	now = now_datetime()
	rows = frappe.get_all(
		GRANT,
		filters={"support_user": user, "status": "Active", "starts_at": ["<=", now]},
		fields=["name", "starts_at", "expires_at"],
		order_by="expires_at desc",
	)
	for row in rows:
		if grant_end(row.starts_at, row.expires_at) > now:
			return row.name
	return None


def has_support_access(user=None, roles=None) -> bool:
	"""True for a Platform Admin whose grant is active. Reads only: see lead_permissions."""
	user = user or frappe.session.user
	roles = frappe.get_roles(user) if roles is None else roles
	return PLATFORM_ADMIN in roles and bool(active_grant(user))


def effective_status(status, starts_at, expires_at) -> str:
	if status == "Active" and grant_end(starts_at, expires_at) <= now_datetime():
		return "Expired"
	return status


# --- The log --------------------------------------------------------------------------------------


def write_log(
	grant, action, user=None, http_method=None, path=None, reference_doctype=None, reference_name=None
):
	"""One line in the Support Access Log, committed at once so a later failure can not lose it."""
	frappe.get_doc(
		{
			"doctype": LOG,
			"grant": grant,
			"user": user or frappe.session.user,
			"timestamp": now_datetime(),
			"action": action,
			"http_method": http_method,
			"path": (path or "")[:PATH_LIMIT],
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		}
	).insert(ignore_permissions=True)


def log_support_request():
	"""before_request hook: write down what a Platform Admin with an active grant asks for."""
	request = frappe.local.request
	user = frappe.session.user
	if not request or user in ("Guest", "Administrator") or PLATFORM_ADMIN not in frappe.get_roles(user):
		return
	grant = active_grant(user)
	if not grant:
		return
	doctype = name = None
	if match := _RESOURCE_PATH.match(request.path):
		doctype, name = match.group("doctype"), match.group("name")
	form = frappe.form_dict
	doctype = doctype or form.get("doctype")
	name = name or form.get("name")
	write_log(
		grant,
		"Request",
		user=user,
		http_method=request.method,
		path=request.path,
		reference_doctype=doctype if isinstance(doctype, str) else None,
		reference_name=name if isinstance(name, str) else None,
	)
	frappe.db.commit()  # a read is not committed by the request, and the line must stay  # nosemgrep


def expire_due_grants():
	"""Mark every grant that has ended as Expired and log it. Scheduler hook, safe to run again."""
	now = now_datetime()
	for row in frappe.get_all(
		GRANT, filters={"status": "Active"}, fields=["name", "support_user", "starts_at", "expires_at"]
	):
		if grant_end(row.starts_at, row.expires_at) <= now:
			frappe.db.set_value(GRANT, row.name, "status", "Expired", update_modified=False)
			write_log(row.name, "Expired", user=row.support_user)


# --- The API for the Company Admin ----------------------------------------------------------------


def _grant_view(row) -> dict:
	return {
		"name": row.name,
		"support_user": row.support_user,
		"support_user_name": frappe.db.get_value("User", row.support_user, "full_name") or row.support_user,
		"granted_by": row.granted_by,
		"duration_minutes": row.duration_minutes,
		"reason": row.reason or "",
		"starts_at": str(row.starts_at),
		"expires_at": str(grant_end(row.starts_at, row.expires_at)),
		"status": effective_status(row.status, row.starts_at, row.expires_at),
		"revoked_at": str(row.revoked_at) if row.revoked_at else None,
	}


@sellos_api(COMPANY_ADMIN)
def list_support_users():
	"""The users a grant can be given to: the enabled Platform Admins of this site."""
	names = frappe.get_all("Has Role", filters={"role": PLATFORM_ADMIN, "parenttype": "User"}, pluck="parent")
	return frappe.get_all(
		"User",
		filters={"name": ["in", names or [""]], "enabled": 1},
		fields=["name as user", "full_name"],
		order_by="full_name asc",
	)


@sellos_api(COMPANY_ADMIN)
def grant_support_access(support_user, duration_minutes, reason=""):
	"""Give a support user read access for a chosen time, 4 hours at most."""
	minutes = cint(duration_minutes)
	if not 1 <= minutes <= MAX_MINUTES:
		frappe.throw(_("Choose a duration from 1 minute to 4 hours."))
	doc = frappe.get_doc(
		{
			"doctype": GRANT,
			"support_user": support_user,
			"duration_minutes": minutes,
			"reason": (reason or "")[:500],
		}
	)
	doc.insert(ignore_permissions=True)
	write_log(doc.name, "Granted", user=frappe.session.user)
	return _grant_view(doc)


@sellos_api(COMPANY_ADMIN)
def revoke_support_access(grant):
	"""End a grant now. A grant that has already ended is returned as it is."""
	doc = frappe.get_doc(GRANT, grant)
	if effective_status(doc.status, doc.starts_at, doc.expires_at) == "Active":
		doc.status = "Revoked"
		doc.revoked_at = now_datetime()
		doc.revoked_by = frappe.session.user
		doc.save(ignore_permissions=True)
		write_log(doc.name, "Revoked", user=frappe.session.user)
	return _grant_view(doc)


@sellos_api(COMPANY_ADMIN)
def list_support_grants():
	"""Every grant, newest first."""
	expire_due_grants()
	rows = frappe.get_all(
		GRANT,
		fields=[
			"name",
			"support_user",
			"granted_by",
			"duration_minutes",
			"reason",
			"starts_at",
			"expires_at",
			"status",
			"revoked_at",
		],
		order_by="creation desc",
		limit_page_length=50,
	)
	return [_grant_view(row) for row in rows]


@sellos_api(COMPANY_ADMIN)
def support_access_log(grant):
	"""The log of one grant, oldest first."""
	if not frappe.db.exists(GRANT, grant):
		frappe.throw(_("That support grant does not exist."), frappe.DoesNotExistError)
	rows = frappe.get_all(
		LOG,
		filters={"grant": grant},
		fields=["user", "timestamp", "action", "http_method", "path", "reference_doctype", "reference_name"],
		order_by="timestamp asc, creation asc",
		limit_page_length=500,
	)
	return [{**row, "timestamp": str(row.timestamp)} for row in rows]
