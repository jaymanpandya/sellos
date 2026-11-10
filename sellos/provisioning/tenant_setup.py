"""Steps that run ON a new company's site, started by the provisioning worker (P1.02).

The worker runs them with `bench execute` on the tenant site. They never see the control site or any
other company. Each is safe to run again. Neither holds a secret: the one-time set password link is
printed once, on a marked line, for the worker to put in the admin's email, and is never stored here.
"""

import json

import frappe

from sellos.access.roles import COMPANY_ADMIN, ensure_roles
from sellos.provisioning.tenant_sites import names

RESULT_MARK = "SELLOS_SETUP_RESULT "
LIMITS_KEY = "sellos_limits"


def _check_site(tenant_id):
	site, _db = names(tenant_id)
	if frappe.local.site != site:
		raise RuntimeError(f"This step belongs to {site}, not {frappe.local.site}.")


def configure(tenant_id, company_name, admin_email, admin_name=None, plan=None, max_users=0):
	"""Roles, company name, the Company Admin user and the plan limits. Printed back as one JSON line."""
	from frappe.installer import update_site_config

	_check_site(tenant_id)
	ensure_roles()

	settings = frappe.get_single("SellOS Settings")
	settings.company_name = company_name
	settings.save(ignore_permissions=True)

	if frappe.db.exists("User", admin_email):
		user = frappe.get_doc("User", admin_email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": admin_email,
				"first_name": (admin_name or company_name or "Admin").strip(),
				"send_welcome_email": 0,
			}
		)
	user.enabled = 1
	user.flags.ignore_permissions = True
	if COMPANY_ADMIN not in {row.role for row in user.get("roles", [])}:
		user.append("roles", {"role": COMPANY_ADMIN})
	# Frappe queues a background job to make the Contact unless it is installing. The job would run
	# after this process ends, so make it inside this save (as sellos.testing.users does, SOS-SETUP-25).
	previous = frappe.flags.in_install
	frappe.flags.in_install = "sellos"
	try:
		user.save()
	finally:
		frappe.flags.in_install = previous

	update_site_config(LIMITS_KEY, {"plan": plan or "", "max_users": int(max_users or 0)})
	frappe.db.commit()  # nosemgrep  bench execute commits too; the read back below must see it
	return report(tenant_id, admin_email)


def report(tenant_id, admin_email):
	_check_site(tenant_id)
	info = {
		"site": frappe.local.site,
		"company_name": frappe.db.get_single_value("SellOS Settings", "company_name"),
		"admin": admin_email,
		"admin_enabled": bool(frappe.db.get_value("User", admin_email, "enabled")),
		"admin_roles": sorted(frappe.get_roles(admin_email)) if frappe.db.exists("User", admin_email) else [],
		"limits": frappe.get_site_config().get(LIMITS_KEY),
	}
	print(RESULT_MARK + json.dumps(info))
	return None


def make_login_link(tenant_id, admin_email):
	"""A one time link for the admin to set a password. Printed once on a marked line, never stored."""
	_check_site(tenant_id)
	user = frappe.get_doc("User", admin_email)
	link = user._reset_password(send_email=False)
	frappe.db.commit()  # nosemgrep  the key must be saved before the email goes out
	print(RESULT_MARK + json.dumps({"path": link[link.index("/update-password") :]}))
	return None
