"""The per company key record (SOS-P1-09).

A key has a scope: "Lead intake" opens the website form endpoint (SOS-P1-09), "Listings read" will open
the listings endpoint (SOS-P4-08, which adds no second key store). A key of one scope never works for
another. Only the SHA-256 hash of the key is saved. The key itself is returned once, when it is made, and
no API ever returns it again. Every company is its own site, so the keys of a site are that company's.
"""

import hashlib

import frappe
from frappe import _

DOCTYPE = "Intake Key"
LEAD_INTAKE = "Lead intake"
LISTINGS_READ = "Listings read"
SCOPES = (LEAD_INTAKE, LISTINGS_READ)


def hash_key(key: str) -> str:
	return hashlib.sha256(key.encode()).hexdigest()


def make_key(scope: str, label: str, replace: bool = False) -> str:
	"""Make a key for the scope and return it. This is the only time it can be read. replace=True
	switches off every active key of the scope first (a rotation)."""
	if scope not in SCOPES:
		frappe.throw(_("Unknown key scope."), frappe.ValidationError)
	if replace:
		for name in frappe.get_all(DOCTYPE, {"scope": scope, "active": 1}, pluck="name"):
			frappe.db.set_value(DOCTYPE, name, "active", 0)
	key = frappe.generate_hash(length=32)
	frappe.get_doc(
		{"doctype": DOCTYPE, "key_label": label, "scope": scope, "key_hash": hash_key(key), "active": 1}
	).insert(ignore_permissions=True)
	return key


def key_valid(given, scope: str) -> bool:
	"""True when `given` is the live key of this scope on this site."""
	if not isinstance(given, str) or not given or len(given) > 128:
		return False
	return bool(frappe.db.exists(DOCTYPE, {"key_hash": hash_key(given), "scope": scope, "active": 1}))


def active_keys(scope: str) -> list[dict]:
	"""The keys of a scope, with no hash and no key."""
	return frappe.get_all(
		DOCTYPE,
		{"scope": scope},
		["name", "key_label", "active", "creation"],
		order_by="creation desc",
	)
