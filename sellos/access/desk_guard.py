"""Keep customer roles out of the Frappe desk (P0.10).

Customers never use the desk. A signed in user who holds a SellOS customer role and is not also a
Platform Admin or System Manager is sent to the web app when they ask for a desk page. This only
redirects page loads. The API stays open, because the web app calls it, and each method checks
its own roles (P1.04).
"""

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

APP_ROUTE = "/sellos"

# Company Admin, Agent, Client and Channel Partner. The Platform Admin runs the control site and
# may use the desk. Default chosen for P0.10, see PROGRESS.md.
CUSTOMER_ROLES = frozenset(
	{
		"SellOS Company Admin",
		"SellOS Agent",
		"SellOS Client",
		"SellOS Channel Partner",
	}
)
DESK_EXEMPT_ROLES = frozenset({"SellOS Platform Admin", "System Manager", "Administrator"})


# Frappe 16 serves the desk at /desk, and /app redirects to it. Both are blocked.
DESK_PREFIXES = ("/app", "/desk")


def is_desk_path(path: str) -> bool:
	return any(path == prefix or path.startswith(prefix + "/") for prefix in DESK_PREFIXES)


def is_blocked(user: str, roles, path: str) -> bool:
	"""True when this user must not see this desk path."""
	if user == "Guest" or not is_desk_path(path):
		return False
	roles = set(roles)
	if roles & DESK_EXEMPT_ROLES:
		return False
	return bool(roles & CUSTOMER_ROLES)


def block_desk():
	"""before_request hook."""
	request = frappe.local.request
	if not request or frappe.session.user == "Guest":
		return
	if is_blocked(frappe.session.user, frappe.get_roles(), request.path):
		raise HTTPException(response=redirect(APP_ROUTE))
