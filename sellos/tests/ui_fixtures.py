"""Server side helpers for the Cypress specs. Run with bench execute, never exposed over HTTP.

cy.bench("sellos.tests.ui_fixtures.<name>", {kwargs}) runs one of these and reads the JSON it
returns from the last line of output. A helper that is not finished raises NotImplementedError on
purpose: the spec that needs it then fails loudly instead of passing on nothing.
"""

import frappe

from sellos.testing.users import PASSWORD, TEST_USERS, ensure_test_users
from sellos.tests import phones


def ensure_role_user(role):
	"""Create or repair the test user for a role and return how to sign in as them.

	Roles are the keys of TEST_USERS: platform_admin, company_admin, agent, channel_partner,
	client and basic.
	"""
	if role not in TEST_USERS:
		raise ValueError(f"Unknown role {role}. Choose one of {', '.join(TEST_USERS)}.")
	ensure_test_users()
	spec = TEST_USERS[role]
	return {"user": spec["email"], "password": PASSWORD, "full_name": spec["first_name"]}


def fresh_phone(seed=1):
	"""A valid Indian mobile for a spec to type, so a spec never holds a literal number."""
	return {"phone": phones.in_mobile(int(seed))}


def prepare_clean_site():
	"""Leave the test site in the state a provisioned company site is in, with the role users made.

	scripts/make-baseline.sh runs this once and saves the result as the clean baseline that every
	gate run starts from.
	"""
	_configure_company_site()
	ensure_test_users()
	# A baseline must be saved, and bench execute is not a request.
	frappe.db.commit()  # nosemgrep


def _configure_company_site():
	"""Set the site up the way provisioning sets up a real company site.

	On a fresh site every CRM call is refused for every user. The code that decides this is in
	sellos.access, so the setup that lifts it belongs there too (the company profile or the
	site type the guard checks). Call it here, and make it the same code provisioning calls, so
	the test site cannot drift from a real one.
	"""
	raise NotImplementedError("Call the provisioning code that makes this a company site. See the docstring.")


def seed_agent_leads():
	"""Make one lead the test agent owns and two they do not. Return {"own": name, "others": [names]}.

	Create them through the same functions the app uses (sellos.crm.api), as the company admin,
	never by inserting rows, so the permissions, the change history and the masking all run.
	"""
	raise NotImplementedError("Implement with the CRM API. See the docstring.")


def seed_client_with_phone(seed=21):
	"""Make a client the test agent can read, with a phone number that changes once.

	Create the client and its lead through sellos.crm.api as the company admin, then change the
	phone through the same API so the change history holds the old and the new number. Return
	{"client": name, "client_name": title, "lead": name, "phone_forms": [...]}, where phone_forms is
	sellos.tests.phones.forms(new number) plus forms(old number), new number first.
	"""
	raise NotImplementedError("Implement with the CRM API. See the docstring.")
