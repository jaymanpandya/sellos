"""Per person interface preferences (docs/DESIGN_SYSTEM.md, "Sidebar"): which sidebar sections a person has closed.

The open or closed choice of each sidebar section is remembered per person on the server, so it follows them to
another browser or phone. It is the person's own setting: each method reads and writes only the signed in user's
own value (a Frappe user default), never anyone else's, and holds no company data. Every role may call both.
"""

import json

import frappe

from sellos.access.registry import sellos_api
from sellos.access.roles import (
	AGENT,
	CHANNEL_PARTNER,
	CLIENT,
	COMPANY_ADMIN,
	PLATFORM_ADMIN,
	SALES_MANAGER,
)

DEFAULT_KEY = "sellos_nav_closed_sections"
# The sidebar sections (frontend/src/areas.js, AREA_ORDER). Anything else is dropped.
SECTIONS = ("sales", "calls", "inventory", "money", "company")
ALL_ROLES = (PLATFORM_ADMIN, COMPANY_ADMIN, AGENT, CLIENT, CHANNEL_PARTNER, SALES_MANAGER)


def _read(user):
	raw = frappe.defaults.get_user_default(DEFAULT_KEY, user=user)
	try:
		value = json.loads(raw or "[]")
	except ValueError:
		value = []
	return [key for key in SECTIONS if key in value] if isinstance(value, list) else []


@sellos_api(*ALL_ROLES)
def get_nav_state():
	"""The sidebar sections the signed in person has closed, as a list of section keys."""
	return {"closed": _read(frappe.session.user)}


@sellos_api(*ALL_ROLES)
def set_nav_state(closed=None):
	"""Remember which sidebar sections the signed in person has closed. Unknown keys are dropped."""
	if isinstance(closed, str):
		closed = frappe.parse_json(closed)
	keep = [key for key in SECTIONS if isinstance(closed, list) and key in closed]
	frappe.defaults.set_user_default(DEFAULT_KEY, json.dumps(keep), user=frappe.session.user)
	return {"closed": keep}
