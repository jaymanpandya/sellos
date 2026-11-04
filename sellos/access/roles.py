"""The five SellOS roles (P1.04). Created from code on install and on every migrate, never in the Desk."""

import frappe

PLATFORM_ADMIN = "SellOS Platform Admin"
COMPANY_ADMIN = "SellOS Company Admin"
AGENT = "SellOS Agent"
CLIENT = "SellOS Client"
CHANNEL_PARTNER = "SellOS Channel Partner"

# role name -> whether the role may open the Frappe desk. Only the Platform Admin may.
ROLES = {
	PLATFORM_ADMIN: 1,
	COMPANY_ADMIN: 0,
	AGENT: 0,
	CLIENT: 0,
	CHANNEL_PARTNER: 0,
}


def ensure_roles():
	"""Create any missing role and keep the desk access flag right. Safe to run again."""
	for role, desk_access in ROLES.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": desk_access}).insert(
				ignore_permissions=True
			)
		elif frappe.db.get_value("Role", role, "desk_access") != desk_access:
			frappe.db.set_value("Role", role, "desk_access", desk_access)


def after_install():
	ensure_roles()


def after_migrate():
	ensure_roles()
