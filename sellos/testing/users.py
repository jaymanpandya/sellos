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

	SOS-SETUP-25: it never writes a Contact that already exists. Saving a User makes Frappe queue a
	create_contact job for after the commit, and the shared bench worker runs it at any moment. If
	this fixture then saved the same Contact, MariaDB 11.8's snapshot isolation refused the write
	(error 1020, "Record has changed since last read in table tabcontact"), a timing race that
	Blocked SOS-P1-06A. So:
	* a user it saves gets its Contact made in the same transaction, synchronously, with no job
	  queued (_save_user sets frappe.flags.in_install, which is what Frappe checks);
	* a user that already exists gets a Contact only when none exists for its email;
	* a user that is already ready is not saved at all, so nothing is written.
	Each write is retried up to 3 times on frappe.QueryDeadlockError (1020 and 1213), from a new
	transaction. Code inside the test runner uses create_test_users() instead, which never commits.
	"""
	for spec in TEST_USERS.values():
		if not _is_ready(spec):
			_with_conflict_retry(lambda spec=spec: _ensure_user(spec, synchronous_contact=True))

	for spec in TEST_USERS.values():
		email = spec["email"]
		if not frappe.db.exists("User", email):
			raise AssertionError(f"Test user {email} was not created")
		if not _contact_for(email):
			_with_conflict_retry(lambda email=email: _create_missing_contact(email))
	return [spec["email"] for spec in TEST_USERS.values()]


# A Contact write is retried this many times after the first try (SOS-SETUP-25).
CONTACT_WRITE_RETRIES = 3


def _with_conflict_retry(write):
	"""Run write(), and on a database conflict roll back and run it again, up to 3 more times.

	Frappe raises QueryDeadlockError for a deadlock (1213) and for a snapshot conflict (1020). The
	read view lives as long as the transaction, so only a rollback lets the next try see the row
	the other connection changed. It commits before the write and after it, so a rollback loses
	nothing else, and only ensure_test_users (bench execute, which commits anyway) calls it.
	"""
	frappe.db.commit()  # keep what the caller made before a rollback could lose it  # nosemgrep
	for attempt in range(CONTACT_WRITE_RETRIES + 1):
		try:
			result = write()
		except frappe.QueryDeadlockError:
			frappe.db.rollback()
			if attempt == CONTACT_WRITE_RETRIES:
				raise
			continue
		frappe.db.commit()  # nosemgrep
		return result


def _contact_for(email):
	from frappe.contacts.doctype.contact.contact import get_contact_name

	return get_contact_name(email)


def _create_missing_contact(email):
	"""Create the Contact of a user that has none. Never called when one exists."""
	if _contact_for(email):
		return
	create_contact(frappe.get_doc("User", email), ignore_mandatory=True)


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


def _ensure_user(spec, synchronous_contact=False):
	"""Create or repair one test user. With synchronous_contact, Frappe makes or updates its
	Contact inside this save instead of queueing a background job for it (SOS-SETUP-25)."""
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
	if synchronous_contact:
		_save_user(user)
	else:
		user.save()


def _save_user(user):
	"""Save a User so Frappe runs its create_contact now, in this transaction, and queues no job.

	User.on_update enqueues create_contact with now=frappe.in_test or frappe.flags.in_install. A
	queued job runs after the commit on the shared bench worker, at a moment nobody controls.
	"""
	previous = frappe.flags.in_install
	frappe.flags.in_install = "sellos"
	try:
		user.save()
	finally:
		frappe.flags.in_install = previous
