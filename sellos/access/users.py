"""Manage users as a Company Admin (SOS-P1-17).

A Company Admin invites users by email with a role, sets each user's Indian mobile number (the number
click to call rings first) and deactivates users who leave, all in the web app and never in the desk.

* The roles on offer are Company Admin, Agent and Channel Partner (`GRANTABLE_ROLES`). Nobody can give the
  Platform Admin role from here, and a user who holds it is not listed and not touched.
* The mobile number is +91 and ten digits, stored in the user's `mobile_no`. An agent without one is shown
  as unable to use click to call.
* Deactivating a user disables the account, ends every session they have and cancels an unused
  invitation, so sign in stops at once. The reply lists the user's open leads and tasks, which SOS-P1-19
  reassigns. Nothing is deleted.
* The invitation is a plain email with a link to set a password. Real mail is SOS-P0-13: until a site can
  send mail the invitation is not sent, the screen says so, and "Send invitation again" sends it later.
"""

import re

import frappe
from frappe import _
from frappe.sessions import clear_sessions
from frappe.utils import cint, validate_email_address

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN, PLATFORM_ADMIN
from sellos.config.setup_wizard import GRANTABLE_ROLES, _max_users, _users

OPEN_LIST_LIMIT = 100
NAME_LIMIT = 60
STANDARD_USERS = ("Administrator", "Guest")
_NATIONAL = re.compile(r"^[6-9]\d{9}$")
_INDIAN = re.compile(r"^\+91[6-9]\d{9}$")


# --- The mobile number ----------------------------------------------------------------------------


def normalize_mobile(value) -> str | None:
	"""+91 and ten digits, or None for a blank. Spaces and dashes are ignored, and ten digits with no
	country code are taken as Indian. Anything else is refused."""
	raw = re.sub(r"[\s\-()]", "", str(value or ""))
	if not raw:
		return None
	if _NATIONAL.match(raw):
		raw = "+91" + raw
	if not _INDIAN.match(raw):
		frappe.throw(_("Enter an Indian mobile number: +91 and ten digits, starting with 6, 7, 8 or 9."))
	return raw


# --- Which users this screen may touch ------------------------------------------------------------


def _roles_of(email) -> set[str]:
	return set(frappe.get_all("Has Role", filters={"parent": email, "parenttype": "User"}, pluck="role"))


def _managed_user(email):
	"""The User this screen may change: holds one of the grantable roles and never the Platform Admin role."""
	email = str(email or "").strip().lower()
	if email in STANDARD_USERS or not frappe.db.exists("User", email):
		frappe.throw(_("There is no user {0}.").format(email), frappe.DoesNotExistError)
	roles = _roles_of(email)
	if PLATFORM_ADMIN in roles or not roles & set(GRANTABLE_ROLES):
		frappe.throw(_("This user can not be managed here."), frappe.PermissionError)
	return frappe.get_doc("User", email)


def _check_role(role):
	if role == PLATFORM_ADMIN:
		frappe.throw(_("The Platform Admin role can not be given here."), frappe.PermissionError)
	if role not in GRANTABLE_ROLES:
		frappe.throw(_("Choose Company Admin, Agent or Channel Partner."))


def _name_part(value, label, required=False):
	value = str(value or "").strip()[:NAME_LIMIT]
	if required and not value:
		frappe.throw(_("Enter the person's {0}.").format(label))
	return value


def _check_mobile_unused(mobile, email):
	if mobile and frappe.db.exists("User", {"mobile_no": mobile, "name": ["!=", email]}):
		frappe.throw(_("Another user already has the mobile number {0}.").format(mobile))


def _check_plan_room():
	limit = _max_users()
	if limit and len(_users()) >= limit:
		frappe.throw(_("Your plan allows {0} users. Remove one or ask for a bigger plan.").format(limit))


# --- Reading --------------------------------------------------------------------------------------


def _open_stage_names() -> list[str]:
	return frappe.get_all("Pipeline Stage", filters={"stage_type": "Open"}, pluck="name")


def _open_leads(email) -> list[dict]:
	stages = _open_stage_names()
	if not stages:
		return []
	return frappe.get_all(
		"Lead",
		filters={"assigned_to": email, "archived": 0, "stage": ["in", stages]},
		fields=["name", "lead_title", "client", "stage"],
		order_by="modified desc",
	)


def _open_tasks(email) -> list[dict]:
	return frappe.get_all(
		"Lead Task",
		filters={"assigned_to": email, "archived": 0, "status": "Open"},
		fields=["name", "title", "lead", "due_at", "due_date"],
		order_by="due_date asc, modified desc",
	)


def _counts(email) -> tuple[int, int]:
	return len(_open_leads(email)), len(_open_tasks(email))


def _status(row) -> str:
	if not row.enabled:
		return "Deactivated"
	return "Active" if row.last_login else "Invited"


def _row(row, roles) -> dict:
	role = next((r for r in GRANTABLE_ROLES if r in roles), None)
	leads, tasks = _counts(row.name)
	mobile = row.mobile_no or None
	return {
		"email": row.name,
		"full_name": row.full_name,
		"first_name": row.first_name,
		"last_name": row.last_name or "",
		"role": role,
		"mobile_no": mobile,
		"enabled": cint(row.enabled),
		"status": _status(row),
		# Click to call rings the user's mobile first, so a user with none can not use it.
		"can_click_to_call": bool(mobile and row.enabled),
		"click_to_call_note": None if mobile else _("No mobile number: can not use click to call."),
		"open_leads": leads,
		"open_tasks": tasks,
	}


def _listed_roles() -> dict[str, set[str]]:
	rows = frappe.get_all(
		"Has Role",
		filters={"role": ["in", [*GRANTABLE_ROLES, PLATFORM_ADMIN]], "parenttype": "User"},
		fields=["parent", "role"],
	)
	roles: dict[str, set[str]] = {}
	for r in rows:
		roles.setdefault(r.parent, set()).add(r.role)
	return roles


def _list() -> list[dict]:
	roles = {
		email: held
		for email, held in _listed_roles().items()
		if PLATFORM_ADMIN not in held and email not in STANDARD_USERS
	}
	if not roles:
		return []
	users = frappe.get_all(
		"User",
		filters={"name": ["in", list(roles)]},
		fields=["name", "full_name", "first_name", "last_name", "mobile_no", "enabled", "last_login"],
		order_by="creation asc",
	)
	return [_row(u, roles[u.name]) for u in users]


def _state() -> dict:
	return {
		"users": _list(),
		"roles": GRANTABLE_ROLES,
		"mail_ready": mail_ready(),
		"max_users": _max_users(),
	}


@sellos_api(COMPANY_ADMIN)
def list_users():
	"""Every Company Admin, Agent and Channel Partner on this site, active or not."""
	return _state()


@sellos_api(COMPANY_ADMIN)
def user_open_work(email):
	"""A user's open leads and tasks: what SOS-P1-19 reassigns when they leave."""
	user = _managed_user(email)
	return _open_work(user.name)


def _open_work(email) -> dict:
	leads, tasks = _open_leads(email), _open_tasks(email)
	return {
		"open_leads": leads[:OPEN_LIST_LIMIT],
		"open_lead_count": len(leads),
		"open_tasks": tasks[:OPEN_LIST_LIMIT],
		"open_task_count": len(tasks),
	}


# --- Inviting -------------------------------------------------------------------------------------


def mail_ready() -> bool:
	"""True when this site has an outgoing email account. Real mail is set up by SOS-P0-13."""
	return bool(frappe.get_all("Email Account", filters={"enable_outgoing": 1}, limit=1))


def _send_invitation(user) -> bool:
	"""Email the user a link to set a password. False when this site can not send mail yet."""
	if not mail_ready():
		return False
	link = user._reset_password()
	company = frappe.db.get_single_value("SellOS Settings", "company_name") or "SellOS"
	message = _(
		"Hello {0},<br><br>You have been invited to {1} on SellOS. Open this link to set your password "
		"and sign in:<br><br><a href='{2}'>{2}</a><br><br>If you were not expecting this, ignore this email."
	).format(frappe.utils.escape_html(user.first_name or "there"), frappe.utils.escape_html(company), link)
	try:
		frappe.sendmail(
			recipients=[user.email],
			subject=_("You are invited to {0} on SellOS").format(company),
			message=message,
			now=True,
		)
	except Exception:
		frappe.log_error("Invitation email failed")
		return False
	return True


@sellos_api(COMPANY_ADMIN)
def invite_user(email, first_name, role, last_name="", mobile_no=""):
	"""Make a user with one role and email them the link to set a password."""
	email = str(email or "").strip().lower()
	first_name = _name_part(first_name, "first name", required=True)
	if not validate_email_address(email):
		frappe.throw(_("Enter a valid email address."))
	_check_role(role)
	mobile = normalize_mobile(mobile_no)
	if frappe.db.exists("User", email):
		frappe.throw(_("{0} already has an account.").format(email))
	_check_mobile_unused(mobile, email)
	_check_plan_room()

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name,
			"last_name": _name_part(last_name, "last name"),
			"mobile_no": mobile,
			"send_welcome_email": 0,
			"roles": [{"role": role}],
		}
	)
	user.flags.ignore_permissions = True
	_save_user(user, insert=True)
	invited = _send_invitation(user)
	return {**_state(), "invited": invited, "email": email}


@sellos_api(COMPANY_ADMIN)
def resend_invitation(email):
	"""Send the invitation again, with a new link. The old link stops working."""
	user = _managed_user(email)
	if not user.enabled:
		frappe.throw(_("Turn this user back on before sending an invitation."))
	if frappe.db.get_value("User", user.name, "last_login"):
		frappe.throw(_("{0} has already signed in.").format(user.name))
	return {**_state(), "invited": _send_invitation(user), "email": user.name}


def _save_user(user, insert=False):
	"""Save a User so Frappe makes its Contact inside this save and queues no job."""
	previous = frappe.flags.in_install
	frappe.flags.in_install = "sellos"
	try:
		user.insert() if insert else user.save()
	finally:
		frappe.flags.in_install = previous


# --- Changing a user ------------------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def save_user(email, values):
	"""Change a user's name, mobile number or role. A blank mobile number clears it."""
	user = _managed_user(email)
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if "first_name" in values:
		user.first_name = _name_part(values["first_name"], "first name", required=True)
	if "last_name" in values:
		user.last_name = _name_part(values["last_name"], "last name")
	if "mobile_no" in values:
		mobile = normalize_mobile(values["mobile_no"])
		_check_mobile_unused(mobile, user.name)
		user.mobile_no = mobile
	role = values.get("role")
	if role:
		_check_role(role)
		if role not in _roles_of(user.name):
			if user.name == frappe.session.user:
				frappe.throw(_("You can not change your own role."))
			kept = [row for row in user.get("roles", []) if row.role not in GRANTABLE_ROLES]
			user.set("roles", [*kept, {"role": role}])
	user.flags.ignore_permissions = True
	_save_user(user)
	return _state()


@sellos_api(COMPANY_ADMIN)
def deactivate_user(email):
	"""Stop a user's sign in at once and list their open leads and tasks.

	The account is disabled, every session is ended and an unused invitation link is cancelled. Their leads
	and tasks stay with them until SOS-P1-19 reassigns them."""
	user = _managed_user(email)
	if user.name == frappe.session.user:
		frappe.throw(_("You can not deactivate yourself."))
	if COMPANY_ADMIN in _roles_of(user.name) and user.enabled and _enabled_admins() <= 1:
		frappe.throw(_("There must be at least one active Company Admin."))
	if user.enabled:
		user.enabled = 0
		user.flags.ignore_permissions = True
		_save_user(user)
	frappe.db.set_value("User", user.name, "reset_password_key", "", update_modified=False)
	clear_sessions(user.name, force=True)
	return {**_state(), "email": user.name, **_open_work(user.name)}


@sellos_api(COMPANY_ADMIN)
def reactivate_user(email):
	"""Let a deactivated user sign in again. Their sessions and invitation stay ended."""
	user = _managed_user(email)
	if not user.enabled:
		_check_plan_room()
		user.enabled = 1
		user.flags.ignore_permissions = True
		_save_user(user)
	return {**_state(), "email": user.name}


def _enabled_admins() -> int:
	admins = frappe.get_all("Has Role", filters={"role": COMPANY_ADMIN, "parenttype": "User"}, pluck="parent")
	return frappe.db.count("User", {"name": ["in", admins or [""]], "enabled": 1})
