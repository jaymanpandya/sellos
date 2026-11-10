"""The control site (P1.01).

The control site is the one site of the Platform Admin. It holds the Tenant, Plan and Provisioning Job
records. It is the same app as a company site, with `sellos_control_site` set to 1 in its
site_config.json. Company users never have an account there, because every company has its own site
and database, and `guard_control_site` refuses anyone who is not a Platform Admin as well.
"""

import frappe
from werkzeug.exceptions import Forbidden

from sellos.access.roles import PLATFORM_ADMIN

# Frappe's built in Administrator is the bench's own login, not a SellOS role.
_ALLOWED_USERS = frozenset({"Administrator"})
# A signed in user must still be able to leave.
_OPEN_PATHS = ("/api/method/logout", "/api/method/ping", "/logout", "/login", "/assets/", "/files/")


def is_control_site() -> bool:
	return bool(frappe.conf.get("sellos_control_site"))


def may_open(user: str, roles) -> bool:
	"""True when this user may use the control site."""
	return user in _ALLOWED_USERS or PLATFORM_ADMIN in set(roles)


def is_open_path(path: str) -> bool:
	return any(path == p.rstrip("/") or path.startswith(p) for p in _OPEN_PATHS)


def is_refused(user: str, roles, path: str) -> bool:
	"""True when this signed in user must be turned away from the control site at this path."""
	if user == "Guest" or is_open_path(path):
		return False  # a guest is left to the login page, which opens nothing
	return not may_open(user, roles)


def guard_control_site():
	"""before_request hook: on the control site, only a Platform Admin may open anything."""
	request = frappe.local.request
	if not request or not is_control_site():
		return
	if is_refused(frappe.session.user, frappe.get_roles(), request.path):
		raise Forbidden("The control site is for the platform administrator only.")
