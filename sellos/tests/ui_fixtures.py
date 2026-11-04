"""Server side helpers for the Cypress specs. Run with bench execute, never exposed over HTTP.

cy.bench("sellos.tests.ui_fixtures.<name>", {kwargs}) runs one of these and reads the JSON it
returns from the last line of output. A helper that is not finished raises NotImplementedError on
purpose: the spec that needs it then fails loudly instead of passing on nothing.
"""

from contextlib import contextmanager

import frappe
from frappe.utils import add_days, add_to_date, now_datetime, today

from sellos.testing.users import PASSWORD, TEST_USERS, _ensure_user, ensure_test_users
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

	scripts/run-tests.sh runs this on every gate run, right after it migrates the clean baseline,
	and scripts/prepare-regression.sh runs it before seeding. The baseline itself is only a clean
	migrated install, so this state is always made by code.
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


# --- The regression dataset (docs/regression/README.md) -------------------------------------------

REGRESSION_PREFIX = "Regression "
REGRESSION_AGENTS = (
	{"email": "regression_agent_two@example.com", "first_name": "Regression Agent Two"},
	{"email": "regression_agent_three@example.com", "first_name": "Regression Agent Three"},
)


@contextmanager
def _as_user(email):
	"""Run the production API as a user, then go back to who was signed in."""
	previous = frappe.session.user
	frappe.set_user(email)
	try:
		yield
	finally:
		frappe.set_user(previous)


def _ensure_regression_agents():
	for agent in REGRESSION_AGENTS:
		_ensure_user({**agent, "roles": ["SellOS Agent"], "desk": False})
	return [agent["email"] for agent in REGRESSION_AGENTS]


def seed_regression_data():
	"""A believable dataset for a clickthrough, built only through sellos.crm.api, never by inserting.

	Every name starts with "Regression ". It runs as each person would: the agents create their own
	leads and log their own work, the Company Admin creates the unassigned lead and the partner's
	leads, so permissions, change history and masking all ran while it was made. Safe to run again:
	it returns the existing set when the first client is already there.

	What it makes today (SOS-P1-06A, the CRM records):
	* Two extra agents (Regression Agent Two and Three) beside the gate agent.
	* Nine leads, each with its client: five owned by three different agents, one unassigned (Company
	  Admin only), two sent by the channel partner, and one archived. Lead pipeline statuses arrive
	  with SOS-P1-07, so for now the leads differ in how far they are along: nothing logged, a call
	  logged, a visit scheduled, a visit done, an overdue task.
	* Activities (every type), tasks (one overdue, one done, the rest open) and site visits
	  (scheduled, done and cancelled).
	* One client whose phone number changed once, so the change history holds the old and the new.
	* One NRI client with an overseas phone number.

	Each task that adds data to the product adds its data here and updates this list.
	Returns {"leads": {title: name}, "agents": [emails], "phone_changed_client": name}.
	"""
	from sellos.crm import api as crm

	admin = TEST_USERS["company_admin"]["email"]
	agent_one = TEST_USERS["agent"]["email"]
	partner = TEST_USERS["channel_partner"]["email"]
	ensure_test_users()
	agent_two, agent_three = _ensure_regression_agents()
	existing = frappe.db.get_value("Client", {"client_name": f"{REGRESSION_PREFIX}Buyer One"}, "name")
	if existing:
		return _regression_summary()

	def make(user, title, client_type, seed, source, assigned_to=None, **client_extra):
		with _as_user(user):
			client = crm.save_client(
				values={
					"client_name": f"{REGRESSION_PREFIX}{title}",
					"client_type": client_type,
					"email": f"regression_{title.lower().replace(' ', '_')}@example.com",
					"city": "Mumbai",
					"phone": phones.in_mobile(seed),
					**client_extra,
				}
			)
			lead = crm.save_lead(
				values={"client": client["name"], "source": source, "assigned_to": assigned_to or user}
			)
		return client["name"], lead["lead"]["name"]

	# Agent one: one lead with a call logged and an open task, one with a visit scheduled.
	client_one, lead_one = make(agent_one, "Buyer One", "Buyer", 101, "Website")
	_, lead_two = make(agent_one, "Buyer Two", "Buyer", 102, "Walk in")
	# Agent two: an overdue task, and a visit that was done.
	_, lead_three = make(agent_two, "Buyer Three", "Buyer", 103, "Referral")
	_, lead_four = make(agent_two, "Investor Four", "Investor", 104, "Facebook")
	# Agent three: an NRI with an overseas number, and a lead with nothing logged yet.
	overseas = {"overseas_phone": phones.ae_mobile(105)}
	if frappe.db.exists("Country", "United Arab Emirates"):
		overseas["country_of_residence"] = "United Arab Emirates"
	_, lead_five = make(agent_three, "NRI Five", "NRI", 106, "Website", **overseas)
	_, lead_six = make(agent_three, "Buyer Six", "Buyer", 107, "Walk in")
	# The Company Admin: an unassigned seller lead, and the two the channel partner sent.
	_, lead_seven = make(admin, "Seller Seven", "Seller", 108, "Phone enquiry", assigned_to=admin)
	make(admin, "Partner Lead One", "Buyer", 109, "Channel Partner", assigned_to=partner)
	make(admin, "Partner Lead Two", "Investor", 110, "Channel Partner", assigned_to=partner)

	with _as_user(agent_one):
		crm.add_activity(lead_one, "Call", "Called, wants a 2 BHK near the station")
		crm.add_activity(lead_one, "WhatsApp", "Sent the brochure")
		crm.save_task(
			values={
				"lead": lead_one,
				"title": "Regression follow up call",
				"due_date": add_days(today(), 2),
				"status": "Open",
				"assigned_to": agent_one,
			}
		)
		crm.save_site_visit(
			values={
				"lead": lead_two,
				"project_name": "Regression Tower",
				"visit_datetime": add_to_date(now_datetime(), days=3),
				"status": "Scheduled",
			}
		)
		crm.add_activity(lead_two, "Meeting", "Met at the office")
	with _as_user(agent_two):
		crm.add_activity(lead_three, "Call", "No answer, try again")
		crm.save_task(
			values={
				"lead": lead_three,
				"title": "Regression overdue callback",
				"due_date": add_days(today(), -3),
				"status": "Open",
				"assigned_to": agent_two,
			}
		)
		crm.save_site_visit(
			values={
				"lead": lead_four,
				"project_name": "Regression Heights",
				"visit_datetime": add_to_date(now_datetime(), days=-1),
				"status": "Done",
			}
		)
		crm.add_activity(lead_four, "Note", "Liked the sea view, asked for the payment plan")
		crm.save_task(
			values={
				"lead": lead_four,
				"title": "Regression send payment plan",
				"due_date": add_days(today(), -1),
				"status": "Done",
				"assigned_to": agent_two,
			}
		)
	with _as_user(agent_three):
		crm.add_activity(lead_five, "Email", "Sent the NRI purchase guide")
		crm.save_site_visit(
			values={
				"lead": lead_five,
				"project_name": "Regression Gardens",
				"visit_datetime": add_to_date(now_datetime(), days=-2),
				"status": "Cancelled",
			}
		)
		crm.set_archived("Lead", lead_six)
	with _as_user(admin):
		crm.add_activity(lead_seven, "Call", "Owner wants to list a 3 BHK")
		# The phone number changes once, so the change history holds the old and the new number.
		crm.save_client(name=client_one, values={"phone": phones.near_in_mobile(101)})

	# bench execute is not a request, and the regression site is read by another process.
	frappe.db.commit()  # nosemgrep
	return _regression_summary()


def _regression_summary():
	leads = frappe.get_all(
		"Lead",
		filters={"lead_title": ["like", f"{REGRESSION_PREFIX}%"]},
		fields=["name", "lead_title", "assigned_to", "archived"],
		order_by="name",
	)
	return {
		"leads": {lead.lead_title: lead.name for lead in leads},
		"agents": [TEST_USERS["agent"]["email"], *[a["email"] for a in REGRESSION_AGENTS]],
		"phone_changed_client": frappe.db.get_value(
			"Client", {"client_name": f"{REGRESSION_PREFIX}Buyer One"}, "name"
		),
	}
