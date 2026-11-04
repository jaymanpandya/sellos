"""Test users for the SellOS test site, used by the gate and by the tests.

Add a user here for every role a story creates. test_every_sellos_role_has_a_test_user fails
when a SellOS role exists without one, so a role can never ship untested.
"""

import frappe
from frappe.core.doctype.user.user import create_contact
from frappe.utils.password import check_password

PASSWORD = "SellOS#Gate2026!x"

# "desk" says whether the user may open the Frappe desk at /desk. Only the platform admin may.
TEST_USERS = {
	"basic": {"email": "sos_test_basic@example.com", "first_name": "Gate Basic", "roles": [], "desk": False},
	"platform_admin": {
		"email": "sos_test_platform_admin@example.com",
		"first_name": "Gate Platform Admin",
		"roles": ["SellOS Platform Admin"],
		"desk": True,
	},
	"company_admin": {
		"email": "sos_test_company_admin@example.com",
		"first_name": "Gate Company Admin",
		"roles": ["SellOS Company Admin"],
		"desk": False,
	},
	"agent": {
		"email": "sos_test_agent@example.com",
		"first_name": "Gate Agent",
		"roles": ["SellOS Agent"],
		"desk": False,
	},
	"channel_partner": {
		"email": "sos_test_channel_partner@example.com",
		"first_name": "Gate Channel Partner",
		"roles": ["SellOS Channel Partner"],
		"desk": False,
	},
	"client": {
		"email": "sos_test_client@example.com",
		"first_name": "Gate Client",
		"roles": ["SellOS Client"],
		"desk": False,
	},
}


def create_test_users():
	"""Create or repair every test user, then read each one back. Raises if one is missing.

	This is the pattern Frappe's own tests use: skip a user that already exists, otherwise insert
	it with frappe.get_doc. It never commits. Inside an IntegrationTestCase the framework rolls
	the users back when the class finishes.
	"""
	for spec in TEST_USERS.values():
		_ensure_user(spec)

	for spec in TEST_USERS.values():
		if not frappe.db.exists("User", spec["email"]):
			raise AssertionError(f"Test user {spec['email']} was not created")
	return [spec["email"] for spec in TEST_USERS.values()]


def ensure_test_users():
	"""The gate fixture, run with bench execute, which commits. The HTTP smoke check needs the
	users to be committed, because the test server is a separate process.

	Saving a user queues its Contact for a background job that runs after the commit. The main
	bench worker would then race the tests. Creating the Contact here, in the same transaction,
	means that job finds it already there and only updates it.
	"""
	emails = create_test_users()
	for email in emails:
		create_contact(frappe.get_doc("User", email), ignore_mandatory=True)
	return emails


def users_for_smoke():
	"""The users the HTTP smoke check logs in as."""
	return [
		{
			"email": spec["email"],
			"password": PASSWORD,
			"roles": spec["roles"],
			"desk": spec["desk"],
		}
		for spec in TEST_USERS.values()
	]


def _is_ready(spec):
	"""True when the user exists, is enabled, holds its roles and accepts the test password."""
	email = spec["email"]
	if not frappe.db.exists("User", email) or not frappe.db.get_value("User", email, "enabled"):
		return False
	if not set(spec["roles"]) <= set(frappe.get_roles(email)):
		return False
	try:
		check_password(email, PASSWORD)
	except frappe.AuthenticationError:
		return False
	return True


def _ensure_user(spec):
	email = spec["email"]
	if _is_ready(spec):
		return  # nothing to repair, so no save and no side effects

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": spec["first_name"],
				"send_welcome_email": 0,
			}
		)

	user.enabled = 1
	user.flags.ignore_password_policy = True
	user.flags.ignore_permissions = True
	user.new_password = PASSWORD

	have = {row.role for row in user.get("roles", [])}
	for role in spec["roles"]:
		if not frappe.db.exists("Role", role):
			raise AssertionError(f"Role {role} does not exist on this site")
		if role not in have:
			user.append("roles", {"role": role})
	user.save()
