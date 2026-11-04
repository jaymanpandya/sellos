"""Keep everyone but the Platform Admin out of the Frappe desk (P0.10, tightened in P1.06).

Only the Platform Admin may open /desk, and only to operate the control site. No customer role ever
gets it (decided by Jayman at Checkpoint A). Anyone else who asks for a desk page is sent to the
web app. This only redirects page loads. The API stays open, because the web app calls it, and each
method checks its own roles (P1.04).
"""

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

APP_ROUTE = "/sellos"

# Frappe's built in Administrator is the bench's own login, not a SellOS role.
DESK_ROLES = frozenset({"SellOS Platform Admin"})
DESK_USERS = frozenset({"Administrator"})


# Frappe 16 serves the desk at /desk, and /app redirects to it. Both are blocked.
DESK_PREFIXES = ("/app", "/desk")


def is_desk_path(path: str) -> bool:
	return any(path == prefix or path.startswith(prefix + "/") for prefix in DESK_PREFIXES)


def is_blocked(user: str, roles, path: str) -> bool:
	"""True when this user must not see this desk path. A guest is left to Frappe's login."""
	if user == "Guest" or not is_desk_path(path):
		return False
	return user not in DESK_USERS and not (set(roles) & DESK_ROLES)


def block_desk():
	"""before_request hook."""
	request = frappe.local.request
	if not request or frappe.session.user == "Guest":
		return
	if is_blocked(frappe.session.user, frappe.get_roles(), request.path):
		raise HTTPException(response=redirect(APP_ROUTE))
