"""Server side helpers for the Cypress specs. Run with bench execute, never exposed over HTTP.

cy.bench("sellos.tests.ui_fixtures.<name>", {kwargs}) runs one of these and reads the JSON it
returns from the last line of output. A helper that is not finished raises NotImplementedError on
purpose: the spec that needs it then fails loudly instead of passing on nothing.
"""

from contextlib import contextmanager

import frappe
from frappe.utils import add_days, add_to_date, now_datetime, today

from sellos.config.company_site import configure_company_site
from sellos.testing.users import (
	PASSWORD,
	TEST_USERS,
	_ensure_user,
	create_test_users,
	ensure_test_users,
)
from sellos.tests import phones


def _test_users():
	"""Make the role users the way the caller's process allows (SOS-SETUP-25).

	Inside the test runner (frappe.in_test) only create_test_users(), which never commits and queues
	no Contact job (Frappe runs it at once while tests run), so an IntegrationTestCase and every test
	that calls seed_agent_leads or seed_client_with_phone keeps its own transaction. Through bench execute (cy.bench, the gate's
	prepare_clean_site) ensure_test_users(), which commits for the browser's separate process.
	"""
	if frappe.in_test:
		return create_test_users()
	return ensure_test_users()


def ensure_role_user(role):
	"""Create or repair the test user for a role and return how to sign in as them.

	Roles are the keys of TEST_USERS: platform_admin, company_admin, agent, channel_partner,
	client and basic.
	"""
	if role not in TEST_USERS:
		raise ValueError(f"Unknown role {role}. Choose one of {', '.join(TEST_USERS)}.")
	_test_users()
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
	_test_users()
	# A baseline must be saved, and bench execute is not a request.
	frappe.db.commit()  # nosemgrep


def _configure_company_site():
	"""Set the site up the way provisioning sets up a real company site.

	It calls sellos.config.company_site.configure_company_site, the code provisioning uses, so the
	test site cannot drift from a real one. (The refusal of every CRM call on a fresh site was not
	a missing setup: the API guard in sellos.access.registry refused declared methods in a process
	that had not imported their module. See load_declared_modules.)
	"""
	configure_company_site()


def set_company_branding(company_name="", logo=""):
	"""Set or clear the company name and logo in SellOS Settings, for the favicon spec."""
	settings = frappe.get_doc("SellOS Settings")
	settings.company_name = company_name or settings.company_name
	settings.logo = logo
	settings.save(ignore_permissions=True)
	frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"company_name": settings.company_name, "logo": settings.logo or ""}


def seed_agent_leads():
	"""Make one lead the test agent owns and two they do not. Return {"own": name, "others": [names]}.

	Create them through the same functions the app uses (sellos.crm.api), as the company admin,
	never by inserting rows, so the permissions, the change history and the masking all run.
	The names returned are the client names, which is the text a lead row shows. Each run makes
	new ones, so a spec never finds a lead left by an earlier run.
	"""
	from sellos.crm import api as crm

	_test_users()
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	tag = frappe.generate_hash(length=6)
	made = {}
	with _as_user(admin):
		for key, owner, seed in (("own", agent, 31), ("other_one", admin, 32), ("other_two", admin, 33)):
			client_name = f"Gate {key.replace('_', ' ').title()} {tag}"
			client = crm.save_client(
				values={"client_name": client_name, "client_type": "Buyer", "phone": phones.in_mobile(seed)}
			)
			crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": owner})
			made[key] = client_name
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"own": made["own"], "others": [made["other_one"], made["other_two"]]}


def seed_client_with_phone(seed=21):
	"""Make a client the test agent can read, with a phone number that changes once.

	Create the client and its lead through sellos.crm.api as the company admin, then change the
	phone through the same API so the change history holds the old and the new number. Return
	{"client": name, "client_name": title, "lead": name, "phone_forms": [...]}, where phone_forms is
	sellos.tests.phones.forms(new number) plus forms(old number), new number first.
	"""
	from sellos.crm import api as crm

	_test_users()
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	seed = int(seed)
	old_number = phones.in_mobile(seed)
	new_number = phones.near_in_mobile(seed)
	client_name = f"Gate Phone {frappe.generate_hash(length=6)}"
	with _as_user(admin):
		client = crm.save_client(
			values={"client_name": client_name, "client_type": "Buyer", "phone": old_number}
		)
		lead = crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": agent})
		crm.save_client(name=client["name"], values={"phone": new_number})
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {
		"client": client["name"],
		"client_name": client_name,
		"lead": lead["lead"]["name"],
		"phone_forms": [*phones.forms(new_number), *phones.forms(old_number)],
	}


def seed_consent_leads():
	"""Make one lead the test agent owns for each consent status (SOS-P1-08).

	Built through sellos.crm.api as the company admin, so the records, the status and the change
	history all come from the production code. Returns {status: lead name} for Consented, Unknown,
	Opted out and Registered DND. Each run makes new ones. remove_seeded_leads removes them.
	"""
	from sellos.crm import api as crm

	_test_users()
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	tag = frappe.generate_hash(length=6)
	made = {}
	with _as_user(admin):
		for seed, status in enumerate(("Consented", "Unknown", "Opted out", "Registered DND"), start=41):
			client = crm.save_client(
				values={
					"client_name": f"Gate Consent {status} {tag}",
					"client_type": "Buyer",
					"phone": phones.in_mobile(seed),
				}
			)
			lead = crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": agent})
			name = lead["lead"]["name"]
			if status == "Consented":
				crm.record_consent(name, "Consent", "https://example.com/evidence/form-41")
			elif status == "Opted out":
				crm.record_opt_out(name, "WhatsApp")
			elif status == "Registered DND":
				crm.record_dnd_result(name, 1)
			made[status] = name
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return made


def remove_seeded_leads():
	"""Remove what seed_agent_leads and seed_client_with_phone committed (tests only, P1.06A).

	The CRM refuses a delete through the app, so this goes to the tables, and only for the clients
	these two fixtures name. Other tests then see the agent's list as they left it. The specs that seed
	run it in their after hook (SOS-SETUP-24), so it returns what it removed for cy.bench to read.
	"""
	clients = frappe.get_all(
		"Client",
		or_filters=[
			["client_name", "like", "Gate Own %"],
			["client_name", "like", "Gate Other %"],
			["client_name", "like", "Gate Phone %"],
			["client_name", "like", "Gate Consent %"],
		],
		pluck="name",
	)
	if not clients:
		return {"clients": 0, "leads": 0}
	leads = frappe.get_all("Lead", filters={"client": ["in", clients]}, pluck="name")
	for doctype in ("Lead Activity", "Lead Task", "Site Visit", "Consent Record"):
		if leads and frappe.get_meta(doctype).has_field("lead"):
			frappe.db.delete(doctype, {"lead": ["in", leads]})
	for doctype, names in (("Lead", leads), ("Client", clients)):
		if names:
			frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ["in", names]})
			frappe.db.delete(doctype, {"name": ["in", names]})
	frappe.db.commit()  # nosemgrep
	return {"clients": len(clients), "leads": len(leads)}


WIZARD_USER_PREFIX = "wizard_spec_"


def reset_setup_wizard(company_name="Pandya Realtors"):
	"""Put the setup wizard back to not started, for the P1.03 spec (and to clean up after it).

	It clears the wizard's progress, the brand colour and logo, the pipeline stages and any user the
	spec made (email starting wizard_spec_), and puts the company name back. Tests only: the app
	itself never deletes a user or a stage this way.
	"""
	settings = frappe.get_doc("SellOS Settings")
	settings.update(
		{
			"company_name": company_name,
			"setup_steps_done": "",
			"setup_complete": 0,
			"brand_color": "",
			"logo": "",
			"contact_phone": "",
			"contact_email": "",
			"city": "",
			"address": "",
		}
	)
	settings.save(ignore_permissions=True)
	frappe.db.delete("Pipeline Stage")
	frappe.db.delete("File", {"attached_to_doctype": "SellOS Settings"})
	for email in frappe.get_all("User", filters={"name": ["like", f"{WIZARD_USER_PREFIX}%"]}, pluck="name"):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"reset": True}


def setup_wizard_result():
	"""Read back what the wizard saved, for the P1.03 spec."""
	settings = frappe.get_doc("SellOS Settings")
	email = frappe.get_all("User", filters={"name": ["like", f"{WIZARD_USER_PREFIX}%"]}, pluck="name")
	return {
		"company_name": settings.company_name,
		"city": settings.city,
		"brand_color": settings.brand_color,
		"logo": settings.logo or "",
		"complete": bool(settings.setup_complete),
		"stages": frappe.get_all("Pipeline Stage", pluck="name", order_by="position asc"),
		"users": {e: sorted(frappe.get_roles(e)) for e in email},
	}


def end_support_grant_now(minutes_ago=5):
	"""Make the newest support grant of the test platform admin run out, as time passing would (P1.13).

	It moves the grant's start and expiry into the past and leaves its status Active, so the spec shows
	that access ends at expiry without the scheduler. Tests only: the app never edits a grant.
	"""
	support_user = TEST_USERS["platform_admin"]["email"]
	name = frappe.db.get_value(
		"Support Grant", {"support_user": support_user}, "name", order_by="creation desc"
	)
	if not name:
		raise ValueError("There is no support grant to end.")
	start = add_to_date(now_datetime(), minutes=-(int(minutes_ago) + 60))
	frappe.db.set_value(
		"Support Grant",
		name,
		{"starts_at": start, "expires_at": add_to_date(start, minutes=60)},
		update_modified=False,
	)
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"grant": name}


def remove_support_grants():
	"""Remove every support grant and log line on the test site (tests only, P1.13).

	The app never deletes them, so this goes to the tables. A spec that grants access runs it in its
	after hook, so a grant never stays active for the backend tests that run next (SOS-SETUP-24).
	"""
	frappe.db.delete("Support Access Log")
	frappe.db.delete("Version", {"ref_doctype": "Support Grant"})
	frappe.db.delete("Support Grant")
	frappe.db.commit()  # nosemgrep
	return {"removed": True}


def remove_control_records():
	"""Remove every Tenant, Plan and Provisioning Job on the test site (tests only, P1.01).

	The app never deletes them, so this goes to the tables. A spec that creates tenants runs it in its
	before and after hooks, so no tenant stays behind for the backend tests that run next.
	"""
	for doctype in ("Provisioning Job", "Tenant", "Plan"):
		frappe.db.delete("Version", {"ref_doctype": doctype})
		frappe.db.delete(doctype)
	frappe.db.commit()  # nosemgrep
	return {"removed": True}


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
	* Two support grants (SOS-P1-13) for the gate platform admin: one the Company Admin ended early
	  and one still active for 2 hours, each with its Granted (and Revoked) line in the access log.

	* Requirements (SOS-P1-15): Buyer One wants a 2 or 3 BHK apartment under construction in Andheri
	  West or Powai for 80 lakh to 1.2 crore, within 3 months. Investor Four wants a ready villa in
	  Alibaug as an investment. The other leads have none.

	* Consent (SOS-P1-08): Buyer One has a Consent record, Buyer Two a live Inquiry, NRI Five a live
	  Application, Buyer Three is Opted out (phone call), Investor Four is Registered DND, and the
	  other leads are Unknown.

	* The company setup wizard (SOS-P1-03) left half way: profile, colours and the default pipeline
	  stages saved, the users step still to do, so it opens on that step.

	* One plan and four tenants on the control site (SOS-P1-01), regressionone to regressionfour, one
	  Requested, one Provisioning, one Active and one Failed, each with its Provisioning Job.

	Each task that adds data to the product adds its data here and updates this list.
	Returns {"leads": {title: name}, "agents": [emails], "phone_changed_client": name}.
	"""
	from sellos.crm import api as crm

	admin = TEST_USERS["company_admin"]["email"]
	agent_one = TEST_USERS["agent"]["email"]
	partner = TEST_USERS["channel_partner"]["email"]
	_test_users()
	agent_two, agent_three = _ensure_regression_agents()
	existing = frappe.db.get_value("Client", {"client_name": f"{REGRESSION_PREFIX}Buyer One"}, "name")
	if existing:
		_seed_requirements(agent_one, agent_two)
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
	# Consent (SOS-P1-08): every status, set through the consent API as the lead's own agent.
	with _as_user(agent_one):
		crm.record_consent(lead_one, "Consent", "https://example.com/regression/consent-form-1")
		crm.record_consent(lead_two, "Inquiry", "https://example.com/regression/website-inquiry-2")
	with _as_user(agent_two):
		crm.record_opt_out(lead_three, "Phone call")
		crm.record_dnd_result(lead_four, 1)
	with _as_user(agent_three):
		crm.record_consent(lead_five, "Application", "https://example.com/regression/application-5")
	with _as_user(admin):
		crm.add_activity(lead_seven, "Call", "Owner wants to list a 3 BHK")
		# The phone number changes once, so the change history holds the old and the new number.
		crm.save_client(name=client_one, values={"phone": phones.near_in_mobile(101)})

	_seed_requirements(agent_one, agent_two)
	_seed_support_grants(admin)
	_seed_control_site()
	_seed_setup_wizard(admin)

	# bench execute is not a request, and the regression site is read by another process.
	frappe.db.commit()  # nosemgrep
	return _regression_summary()


def _seed_requirements(agent_one, agent_two):
	"""What two buyers want (SOS-P1-15), saved through the lead API by the agent who owns each lead.

	Buyer One wants a 2 or 3 BHK apartment under construction; Investor Four wants a ready plot or
	villa as an investment. Safe to run again: a lead that already has a budget is left alone.
	"""
	from sellos.crm import api as crm

	wants = (
		(
			agent_one,
			"Buyer One",
			{
				"budget_from": 8000000,
				"budget_to": 12000000,
				"configuration": ["2 BHK", "3 BHK"],
				"property_type": "Apartment",
				"preferred_localities": ["Andheri West", "Powai"],
				"purpose": "End use",
				"timeline": "Within 3 months",
				"possession": "Under construction",
			},
		),
		(
			agent_two,
			"Investor Four",
			{
				"budget_from": 20000000,
				"budget_to": 30000000,
				"configuration": ["4 BHK and above"],
				"property_type": "Villa",
				"preferred_localities": ["Alibaug"],
				"purpose": "Investment",
				"timeline": "3 to 6 months",
				"possession": "Ready",
			},
		),
	)
	for user, title, values in wants:
		client = frappe.db.get_value("Client", {"client_name": f"{REGRESSION_PREFIX}{title}"}, "name")
		lead = frappe.db.get_value("Lead", {"client": client}, ["name", "budget_from"], as_dict=True)
		if lead and not lead.budget_from:
			with _as_user(user):
				crm.save_lead(name=lead.name, values=values)


def _seed_support_grants(admin):
	"""Two support grants, through the production API (SOS-P1-13): one ended early, one still active."""
	from sellos.access import support

	support_user = TEST_USERS["platform_admin"]["email"]
	with _as_user(admin):
		ended = support.grant_support_access(support_user, 60, "Regression help with an import")
		support.revoke_support_access(ended["name"])
		support.grant_support_access(support_user, 120, "Regression walkthrough of the leads report")


def _seed_setup_wizard(admin):
	"""A setup wizard left half way (SOS-P1-03): profile, colours and stages saved, users not yet.

	Run through the production API as the Company Admin, so the wizard opens on its last step. It keeps
	the company's own name and the SellOS brand colour, so the rest of the app looks the same.
	"""
	from sellos.config import setup_wizard

	if frappe.db.count("Pipeline Stage") or setup_wizard.is_setup_complete():
		return
	with _as_user(admin):
		name = frappe.db.get_single_value("SellOS Settings", "company_name")
		setup_wizard.save_profile({"company_name": name, "city": "Mumbai"})
		setup_wizard.save_branding(setup_wizard.DEFAULT_BRAND_COLOR)
		setup_wizard.save_stages(setup_wizard.DEFAULT_STAGES)


def _seed_control_site():
	"""One plan and four tenants, one in each status, as the Platform Admin (SOS-P1-01).

	The tenants are made and moved through the Document API with the Platform Admin's own
	permissions, so the status order and the permission rules ran while it was made.
	"""
	platform_admin = TEST_USERS["platform_admin"]["email"]
	if frappe.db.exists("Tenant", "regressionone"):
		_settle_seed_jobs(platform_admin)
		return
	with _as_user(platform_admin):
		frappe.get_doc(
			{"doctype": "Plan", "plan_name": f"{REGRESSION_PREFIX}Starter", "max_users": 5}
		).insert()
		path = {
			"regressionone": [],
			"regressiontwo": ["Provisioning"],
			"regressionthree": ["Provisioning", "Active"],
			"regressionfour": ["Provisioning", "Failed"],
		}
		for tenant_id, steps in path.items():
			tenant = frappe.get_doc(
				{
					"doctype": "Tenant",
					"tenant_id": tenant_id,
					"company_name": f"{REGRESSION_PREFIX}{tenant_id[10:].title()} Realty",
					"admin_email": f"{tenant_id}@example.com",
					"plan": f"{REGRESSION_PREFIX}Starter",
				}
			).insert()
			for step in steps:
				tenant.status = step
				tenant.save()
	_settle_seed_jobs(platform_admin)


def _settle_seed_jobs(platform_admin):
	"""Move each seeded tenant's job to its tenant's status, so no job is left waiting to be worked.

	The provisioning worker (SOS-P1-02) takes the oldest Requested job. A job left Requested for a tenant
	that is already Active or Failed would be picked up, and fail the status order. Safe to run again.
	"""
	with _as_user(platform_admin):
		for tenant_id in ("regressiontwo", "regressionthree", "regressionfour"):
			tenant_status = frappe.db.get_value("Tenant", tenant_id, "status")
			for job_name in frappe.get_all(
				"Provisioning Job", filters={"tenant": tenant_id, "status": "Requested"}, pluck="name"
			):
				job = frappe.get_doc("Provisioning Job", job_name)
				job.flags.ignore_permissions = True
				for step in ("Provisioning", tenant_status):
					if job.status != step:
						job.status = step
						job.save()


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
