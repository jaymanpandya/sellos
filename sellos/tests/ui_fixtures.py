"""Server side helpers for the Cypress specs. Run with bench execute, never exposed over HTTP.

cy.bench("sellos.tests.ui_fixtures.<name>", {kwargs}) runs one of these and reads the JSON it
returns from the last line of output. A helper that is not finished raises NotImplementedError on
purpose: the spec that needs it then fails loudly instead of passing on nothing.
"""

from contextlib import contextmanager

import frappe
from frappe.utils import add_days, add_to_date, get_datetime, now_datetime, today

from sellos.config.company_site import configure_company_site
from sellos.crm import pipeline
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


def seed_caller_queue():
	"""The leads the caller queue spec needs (SOS-P2-09), through sellos.crm.api as the company admin. The
	test agent owns one lead in each case: Gate Consent Soon (a live Inquiry, 7 days), Gate Consent Months (a
	live Application, 3 months), Gate Consent Forever (a Consent record, no expiry), Gate Consent Unknown,
	Gate Consent Opted out and Gate Consent Dnd. Returns {key: lead name} and {key: client name}.
	remove_seeded_leads removes them (the names start with Gate Consent)."""
	from sellos.crm import api as crm

	_test_users()
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	tag = frappe.generate_hash(length=6)
	leads, titles = {}, {}
	with _as_user(admin):
		for seed, key in enumerate(("soon", "months", "forever", "unknown", "opted", "dnd"), start=81):
			title = f"Gate Consent Queue {key.title()} {tag}"
			client = crm.save_client(
				values={"client_name": title, "client_type": "Buyer", "phone": phones.in_mobile(seed)}
			)
			lead = crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": agent})
			name = lead["lead"]["name"]
			evidence = "https://example.com/evidence/queue"
			if key == "soon":
				crm.record_consent(name, "Inquiry", evidence)
			elif key == "months":
				crm.record_consent(name, "Application", evidence)
			elif key == "forever":
				crm.record_consent(name, "Consent", evidence)
			elif key == "opted":
				crm.record_opt_out(name, "WhatsApp")
			elif key == "dnd":
				crm.record_dnd_result(name, 1)
			leads[key], titles[key] = name, title
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"leads": leads, "titles": titles}


def seed_board_leads():
	"""Make the leads the pipeline board and list filter spec needs (SOS-P1-24), through sellos.crm.api
	as the company admin. The test agent owns three: Gate Board Agent A (Referral, Qualified, budget up to
	40 lakh, called yesterday), Gate Board Agent B (Website, Qualified, budget up to 60 lakh, opted out) and
	Gate Board Old (Website, New, made 30 days ago with no activity, so it is untouched). The company admin
	owns Gate Board Admin. Returns the client names and the budgets. Each run makes new ones, and
	remove_seeded_leads removes them."""
	from frappe.utils import add_days, now_datetime

	from sellos.crm import api as crm

	_test_users()
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	tag = frappe.generate_hash(length=6)
	names = {}
	with _as_user(admin):
		for key, owner, seed, source, budget, stage in (
			("agent_a", agent, 51, "Referral", 4000000, "Qualified"),
			("agent_b", agent, 52, "Website", 6000000, "Qualified"),
			("old", agent, 53, "Website", None, None),
			("admin", admin, 54, "Referral", 9000000, None),
		):
			client_name = f"Gate Board {key.replace('_', ' ').title()} {tag}"
			client = crm.save_client(
				values={"client_name": client_name, "client_type": "Buyer", "phone": phones.in_mobile(seed)}
			)
			values = {"client": client["name"], "source": source, "assigned_to": owner}
			if budget:
				values["budget_to"] = budget
			lead = crm.save_lead(values=values)["lead"]["name"]
			if stage:
				crm.move_lead_stage(lead, stage)
			names[key] = (client_name, lead)
		crm.add_activity(names["agent_a"][1], "Call", activity_date=add_days(now_datetime(), -1))
		crm.record_opt_out(names["agent_b"][1], "Phone call")
	frappe.db.set_value(
		"Lead", names["old"][1], "creation", add_days(now_datetime(), -30), update_modified=False
	)
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {
		**{key: value[0] for key, value in names.items()},
		"leads": {key: value[1] for key, value in names.items()},
		"qualified_total": 10000000,
		"agent_name": TEST_USERS["agent"]["first_name"],
		"agent_email": agent,
	}


def reset_follow_up_settings():
	"""Put the untouched days back to the default (tests only, SOS-P1-22): the follow up spec changes the
	company's setting through the screen and restores it here, even when it fails."""
	frappe.db.set_single_value("SellOS Settings", "untouched_days", 0)
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"untouched_days": 3}


def seed_duplicate_clients():
	"""Make what the duplicate spec needs (SOS-P1-16), through sellos.crm.api as the company admin.

	* own: a client with an email whose lead is the test agent's.
	* hidden: a client with an email and a phone whose only lead is the company admin's, so the test
	  agent cannot see it.
	* twin A and B: two clients with a lead each, for the company admin to merge.
	Returns the names, emails, masked numbers and every spelling of the full numbers (which the
	spec checks are never shown to the agent). Each run makes new ones, named so that
	remove_seeded_leads removes them.
	"""
	from sellos.crm import api as crm
	from sellos.crm.base import mask_phone

	_test_users()
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	tag = frappe.generate_hash(length=6).lower()
	made = {}
	with _as_user(admin):
		for key, assignee, seed in (("own", agent, 71), ("hidden", admin, 72)):
			name = f"Gate {'Own' if key == 'own' else 'Other'} Dup {tag}"
			number = phones.in_mobile(seed)
			client = crm.save_client(
				values={
					"client_name": name,
					"client_type": "Buyer",
					"email": f"dup_{key}_{tag}@example.com",
					"phone": number,
				}
			)
			crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": assignee})
			made[f"{key}_name"] = name
			made[f"{key}_email"] = f"dup_{key}_{tag}@example.com"
			made[f"{key}_masked"] = mask_phone(number)
			made[f"{key}_phone_forms"] = phones.forms(number)
		for letter, seed in (("A", 73), ("B", 74)):
			name = f"Gate Own Twin {letter} {tag}"
			client = crm.save_client(
				values={"client_name": name, "client_type": "Buyer", "phone": phones.in_mobile(seed)}
			)
			lead = crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": admin})
			crm.add_activity(lead["lead"]["name"], "Call", f"Twin {letter} first call")
			key = f"twin_{letter.lower()}"
			made[f"{key}_name"] = name
			made[f"{key}_client"] = client["name"]
			made[f"{key}_lead"] = lead["lead"]["name"]
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return made


def remove_seeded_leads():
	"""Remove what seed_agent_leads and seed_client_with_phone committed (tests only, P1.06A), and the
	Gate Buyer lead leads_by_role.cy.js makes through the form. Its phone comes from fresh_phone with a
	fixed seed, so a lead left behind would meet the next run with a duplicate warning (SOS-P1-16).

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
			["client_name", "like", "Gate Buyer %"],
			["client_name", "like", "Gate Team %"],
			["client_name", "like", "Gate Board %"],
			["client_name", "like", "Gate Notify %"],
			["client_name", "like", "Gate Assign %"],
			["client_name", "like", "Gate Import %"],
			["client_name", "like", "Gate Today %"],
			["client_name", "like", "Gate Enquiry %"],
		],
		pluck="name",
	)
	if not clients:
		return {"clients": 0, "leads": 0}
	leads = frappe.get_all("Lead", filters={"client": ["in", clients]}, pluck="name")
	if leads:
		frappe.db.delete("Lead Stage Change", {"parent": ["in", leads]})
		frappe.db.delete("App Notification", {"lead": ["in", leads]})  # SOS-P1-23
		frappe.db.delete("Lead Assignment", {"lead": ["in", leads]})  # SOS-P1-19
	for doctype in ("Lead Activity", "Lead Task", "Site Visit", "Consent Record"):
		if leads and frappe.get_meta(doctype).has_field("lead"):
			frappe.db.delete(doctype, {"lead": ["in", leads]})
	for doctype, names in (("Lead", leads), ("Client", clients)):
		if names:
			frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ["in", names]})
			frappe.db.delete(doctype, {"name": ["in", names]})
	frappe.db.commit()  # nosemgrep
	return {"clients": len(clients), "leads": len(leads)}


def _remove_notifications_of_test_users():
	emails = [spec["email"] for spec in TEST_USERS.values()]
	frappe.db.delete("App Notification", {"recipient": ["in", emails]})


def seed_notifications():
	"""Make the notifications the bell spec needs (SOS-P1-23), through sellos.crm.api, so each one is the
	one the production code made. The test agent is given Gate Notify A and then Gate Notify B by the
	company admin (two Lead assigned notifications, B the newer). The test agent then gives the company
	admin Gate Notify C, which notifies the admin and not the agent. Returns the client names and leads.
	Every notification of the test users is cleared first. remove_gate_notifications removes what this makes."""
	from sellos.crm import api as crm

	_test_users()
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	_remove_notifications_of_test_users()
	tag = frappe.generate_hash(length=6)
	made = {}
	for key, maker, assignee, seed in (
		("a", admin, agent, 61),
		("b", admin, agent, 62),
		("c", agent, admin, 63),
	):
		name = f"Gate Notify {key.upper()} {tag}"
		with _as_user(maker):
			client = crm.save_client(
				values={"client_name": name, "client_type": "Buyer", "phone": phones.in_mobile(seed)}
			)
			lead = crm.save_lead(
				values={"client": client["name"], "source": "Website", "assigned_to": assignee}
			)
		made[key] = {"client_name": name, "lead": lead["lead"]["name"]}
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return made


def reassign_gate_notify_lead(lead):
	"""As the company admin, give a seeded lead to the test channel partner (SOS-P1-23), so its agent loses
	it and is told it was reassigned away."""
	from sellos.crm import api as crm

	with _as_user(TEST_USERS["company_admin"]["email"]):
		crm.reassign_lead(lead, TEST_USERS["channel_partner"]["email"])
	frappe.db.commit()  # nosemgrep
	return {"lead": lead}


def remove_gate_notifications():
	"""Remove what seed_notifications committed (tests only, SOS-P1-23): the leads, and every
	notification of the test users."""
	removed = remove_seeded_leads()
	_remove_notifications_of_test_users()
	frappe.db.commit()  # nosemgrep
	return removed


def remove_gate_lead_sources():
	"""Remove what the lead source spec committed (tests only, SOS-P1-20): its clients, their leads and
	the sources named Gate Source. The CRM refuses a delete through the app, so this goes to the tables."""
	clients = frappe.get_all("Client", filters={"client_name": ["like", "Gate Source %"]}, pluck="name")
	leads = frappe.get_all("Lead", filters={"client": ["in", clients]}, pluck="name") if clients else []
	if leads:
		frappe.db.delete("Lead Stage Change", {"parent": ["in", leads]})
	for doctype, names in (("Lead", leads), ("Client", clients)):
		if names:
			frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ["in", names]})
			frappe.db.delete(doctype, {"name": ["in", names]})
	sources = frappe.get_all("Lead Source", filters={"name": ["like", "Gate Source %"]}, pluck="name")
	if sources:
		frappe.db.delete("Version", {"ref_doctype": "Lead Source", "docname": ["in", sources]})
		frappe.db.delete("Lead Source", {"name": ["in", sources]})
	frappe.db.commit()  # nosemgrep
	return {"clients": len(clients), "leads": len(leads), "sources": len(sources)}


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
	# SOS-P1-07: every lead has a stage, so the stages go back to the eleven and a lead whose stage was
	# renamed or removed goes back to New.
	frappe.db.delete("Pipeline Stage")
	pipeline.ensure_default_stages()
	frappe.db.sql(
		"update `tabLead` set stage = %s where stage is null or stage not in (select name from `tabPipeline Stage`)",
		(pipeline.first_stage(),),
	)
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


TELEPHONY_FAKE_ID = "FAKEOK-REGRESSION"
TELEPHONY_FAKE_TOKEN = "regression-telephony-token"
TELEPHONY_SEED = 2201


def landline_022(seed):
	"""A 022 number for a seed: 022 and the last eight digits of the seed's fake mobile number."""
	return "022" + phones.in_mobile(seed)[-8:]


def use_fake_telephony_provider(on=True):
	"""Make the test site's Telephony Settings talk to the fake provider, or stop (SOS-P2-01).

	The provider is a hidden field of Telephony Settings, read from the database so the web server
	sees the change at once. The real provider is never called from a test site, so a spec that
	presses Test connection turns the fake on first.
	"""
	frappe.db.set_single_value("Telephony Settings", "provider", "fake" if on else "")
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"fake_provider": bool(on)}


def telephony_landline():
	"""A 022 number for a browser spec to type, so the spec holds no number of its own (SOS-P2-01)."""
	number = landline_022(TELEPHONY_SEED)
	stored = phones.in_mobile(TELEPHONY_SEED)[:3] + "22" + number[-8:]
	return {"number": number, "stored": stored}


def remove_telephony_settings():
	"""Clear the saved Telephony Settings, keys and fake provider included (tests only, SOS-P2-01).

	The keys sit in the encrypted password table, so a spec that saves them runs this in its after
	hook and no key stays on the site for the backend tests that run next. The caches are cleared
	too, because the web server is another process and would otherwise keep the old values.
	"""
	frappe.db.delete("__Auth", {"doctype": "Telephony Settings"})
	frappe.db.delete("Singles", {"doctype": "Telephony Settings"})
	frappe.db.delete("Version", {"ref_doctype": "Telephony Settings"})
	frappe.db.commit()  # nosemgrep
	frappe.clear_document_cache("Telephony Settings", "Telephony Settings")
	frappe.clear_cache(doctype="Telephony Settings")
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

	* The caller queue (SOS-P2-09): Regression Queue Application, a gate agent lead with a live Application
	  consent (three months), beside Buyer Two's Inquiry (seven days) and Buyer One's Consent (no expiry).

	* Two sales teams (SOS-P1-18): Regression Team North, run by the Sales Manager test user with the gate
	  agent and Regression Agent Two, and Regression Team South, run by Regression Manager Two with
	  Regression Agent Three. The Sales Manager sees the first two agents' leads and not the third's.
	* A bought list (SOS-P1-12), imported by the Company Admin through the import API: Regression Bought
	  One and Regression Bought Two (the second also listed again under another name in the same file,
	  merged into one), both from the source Bought list. One is Unknown and Two is Registered DND, each
	  with its amber warning. They are unassigned, so only the Company Admin sees them.
	* Requirements (SOS-P1-15): Buyer One wants a 2 or 3 BHK apartment under construction in Andheri
	  West or Powai for 80 lakh to 1.2 crore, within 3 months. Investor Four wants a ready villa in
	  Alibaug as an investment. The other leads have none.

	* Consent (SOS-P1-08): Buyer One has a Consent record, Buyer Two a live Inquiry, NRI Five a live
	  Application, Buyer Three is Opted out (phone call), Investor Four is Registered DND, and the
	  other leads are Unknown.

	* Duplicates (SOS-P1-16): Regression Twin A and Regression Twin B are the same person entered twice,
	  each with a lead and an activity, for the Company Admin to merge. Every client's email is
	  regression_<title>@example.com in lower case with underscores, so a duplicate warning can be
	  tried by typing one, for example regression_buyer_two@example.com (the agent's own client) and
	  regression_buyer_three@example.com (another agent's, which the first agent cannot see).

	* Lead sources (SOS-P1-20): the eight standard sources, Regression Roadshow (added by the company),
	  Regression Old Hoarding (disabled, so no picker offers it), and Regression Buyer Three on the
	  Roadshow source under the campaign Diwali 2026 hoardings. Seller Seven came by Missed call and the
	  two partner leads by Channel partner.

	* The buyer pipeline (SOS-P1-07): the eleven stages, and the regression leads moved along them by
	  their own agents through the lead API: Buyer One Qualified, Buyer Two Site visit booked, Buyer
	  Three (Opted out) and Investor Four (Registered DND) Contacted, each with its warning in the
	  stage change log, NRI Five Nurture. The rest stay on New.

	* Call outcomes (SOS-P1-21): the seven standard outcomes and the standard lost reasons, Regression
	  Sent brochure (an outcome the company added: it needs a follow up and suggests Contacted),
	  Regression Price too high (a lost reason the company added), and one call Buyer Two's agent
	  logged by hand on Regression Buyer Two (Busy, two minutes, with its follow up tomorrow).

	* Users (SOS-P1-17): Regression New Agent (invited, with an Indian mobile number, never signed in),
	  Regression Agent No Mobile (invited with no number, so shown as unable to use click to call) and
	  Regression Former Agent (deactivated, SOS-P1-19: their one open lead and one open task were handed to
	  Regression Agent No Mobile, so nothing is left with the inactive user).
	  All three are made through the Company Admin's invite and deactivate methods, with mail switched off.

	* Telephony Settings (SOS-P2-01): the Plivo India account saved with fake keys, a 022 number
	  made by landline_022(TELEPHONY_SEED), and the fake provider switched on, so Test connection reports success.

	* Click to call (SOS-P2-07): the gate agent has the Indian mobile number made by
	  phones.in_mobile(CLICK_TO_CALL_SEED), set by the Company Admin through the users API, so the Call
	  button on a lead rings the agent's phone first through the fake provider and shows the lead's warning.

	* Calling hours and the do not call list (SOS-P2-10): calling hours of 9:00 am to 9:00 pm, Monday to
	  Saturday, saved but switched off (so the regression calls work at any time), and a do not call list
	  holding the number of Regression DND Listed, a lead of the gate agent that is therefore Registered DND
	  with an amber warning on the lead, the caller queue and the call log. Made through the Company Admin's
	  production methods.

	* The company setup wizard (SOS-P1-03) left half way: profile, colours and the eleven pipeline
	  stages saved, the users step still to do, so it opens on that step.

	* One plan and four tenants on the control site (SOS-P1-01), regressionone to regressionfour, one
	  Requested, one Provisioning, one Active and one Failed, each with its Provisioning Job.

	* The pipeline board and list filters (SOS-P1-24): Regression Dormant Eight, a Referral lead of the gate
	  agent on New with a budget up to 70 lakh, made 30 days ago with nothing logged, so the board and the
	  list mark it as having no activity for 7 days. The other regression leads are recent, so only this
	  one is marked. The board and the filters use the stages, budgets, sources, consent statuses and
	  teams above.

	* In-app notifications (SOS-P1-23): the leads the Company Admin gave the agents above each notified
	  their agent (Lead assigned), a Regression Tomorrow Heights site visit is scheduled tomorrow on
	  Buyer One, and the scheduler's follow up and site visit functions are run once, so the gate agent's
	  bell holds Lead assigned, Follow up due or overdue and Site visit tomorrow notifications.

	* Follow ups (SOS-P1-22): the gate agent has an overdue follow up on Regression Buyer Two (Regression
	  chase the site visit, two hours ago) and one due in ten minutes on Regression Buyer One (Regression
	  ring back soon), so the leads list shows them, the Overdue filter finds Buyer Two, and the
	  scheduler's reminder function tells the agent of both. Regression Dormant Eight has no open follow up
	  and is flagged untouched after the Company Admin's number of days (3).

	* Site visits (SOS-P1-25): tomorrow the gate agent has Regression Tomorrow Heights on Regression Buyer
	  One (Not confirmed, and Buyer One stays on Qualified) and Regression Skyline Walkthrough on Regression
	  Buyer Two (Confirmed), and Regression Agent Two has Regression Lakeside Tour on Regression Buyer Three
	  (Not confirmed). The gate agent's calendar and list of tomorrow's visits hold their own two, the Sales
	  Manager sees all three and the Company Admin sees all three. Regression Buyer Two is on Site visit
	  booked, so marking its visit done offers a next stage.

	* The Today screen (SOS-P1-26): it reads the data above. For the gate agent it lists the overdue
	  Regression chase the site visit and the follow up Regression ring back soon (due in ten minutes, so
	  it is on Today until midnight), the new lead Regression Dormant Eight, today's visit Regression Noon
	  Walkthrough on Regression Buyer Two (at noon today, made here) and tomorrow's two visits to
	  confirm. The Sales Manager sees the same by agent for Regression Team North.

	* Call reports (SOS-P2-11): seven calls on Regression Buyer One to Four and Regression Queue Application,
	  placed through the fake provider and its last event (REPORT_CALL_PLAN): Service and Transactional,
	  completed, no answer, busy and failed, by the gate agent and the Company Admin, one 40 days ago, so the
	  Company Admin's call reports show cost by agent and by purpose, a connect rate, talk time and consent
	  coverage for the last 30 days, and each figure lists its calls.

	* Channel partner firms (SOS-P7-01): four firms invited by the Company Admin through the invite method
	  (mail off) and completed by each contact person through the partner methods: Regression Firm Invited
	  (waiting for its details), Regression Firm Pending (details and agreement in, waiting for approval),
	  Regression Firm Approved and Regression Firm Suspended (reason "Regression: left the business").
	  Each has a partner code, a status log, a PAN and a private signed agreement the Company Admin sees.
	* Partner registrations (SOS-P7-02): three buyers the contact person of Regression Firm Approved registers
	  through register_buyer: Regression Partner Buyer One (Registered, waiting), Two (Approved by the Company
	  Admin, so protected, with the buyer's agreement recorded) and Three (Rejected with a reason).

	* Towers (SOS-P7-05): Regression Towers (RERA number P51800099002, Powai, Mumbai) with Tower A, floors 1 to 3,
	  the Available 1 BHK units 101 to 103 on floor 1, the possession date 31 March 2028 and the amenities
	  Swimming pool and Gym, made by the Company Admin through the structure API.

	* Unit grid (SOS-P7-06): Regression Grid (RERA number P51800099003, Andheri, Mumbai) with Tower G, floors 1
	  and 2, made through the structure API: G101 and G103 (2 BHK) and G201 (1 BHK) Available, G102 (3 BHK)
	  held by the gate agent for Regression Buyer One through the hold API, and G104 (2 BHK) blocked by the
	  Company Admin with the reason "Regression: legal hold".

	* Pricing (SOS-P7-07): Regression Pricing (RERA number P51800099004, Powai, Mumbai) with unit 1501 (2 BHK,
	  650 sq ft carpet area, floor 12, 1 parking slot), the company percentages stamp duty 6, registration 1 and
	  GST 5, the price list Regression Price List in force from 1 January 2026 (Rs 12,000 per sq ft, floor rise
	  Rs 100 per sq ft above floor 4, Garden at Rs 150 per sq ft, Parking Rs 4,00,000 a slot, Development Rs
	  2,50,000), the payment plans Regression Construction Plan (20, 30 and 50 percent) and Regression Time Plan
	  (10 percent now, 90 percent after 30 days), and one cost sheet of unit 1501 made by the gate agent with the
	  Construction plan and the Garden charge, total Rs 1,01,55,600. All made through the pricing and cost sheet APIs.

	* Listings (SOS-P4-02): the published Primary listing Regression Primary 2 BHK (unit 1501 of Regression
	  Pricing, Rs 1,05,00,000), the published Direct listing Regression Direct Resale (the property Regression
	  Resale Flat, Rs 82,00,000) and the Partner draft Regression Partner Draft with no price or description,
	  all made by the gate agent through the listing API.

	* Inventory (SOS-P4-01): Regression Developer and its project Regression Heights (RERA number
	  P51800099001, Mumbai), made by the Company Admin through the inventory API, with four units: 1201 (2 BHK,
	  Available), 1202 (2 BHK, Available), 1301 (3 BHK, Held by the gate agent, with its reason in the status
	  log) and 1302 (3 BHK, Sold). The agent also made a secondary property, Regression Resale Flat in Pune.

	* The inbound opt in route (SOS-P2-08), made through sellos.crm.intake.take, the one intake function:
	  Regression Enquiry One (the enquiry page, Consented with an inquiry record for 7 days),
	  Regression Enquiry Stop (the enquiry page, "Stop contacting me": Opted out, red warning) and a lead
	  from a missed call to the 022 number, a new lead on the New stage whose name is "Caller" and the last
	  three digits of its number.

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
		_seed_twin_clients(admin, agent_one)
		_seed_lead_sources(admin)
		_seed_pipeline_stages()
		_seed_call_outcomes(admin, agent_one)
		_seed_users(admin)
		_seed_dormant_lead(admin, agent_one)
		_seed_follow_ups(agent_one)
		_seed_notifications(agent_one)
		_seed_site_visits(agent_one, agent_two)
		_seed_call_reports_regression()
		_seed_partner_firms(admin)
		_seed_partner_registrations(admin)
		_seed_inventory(admin, agent_one)
		_seed_inbound_opt_in()
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
	_, lead_seven = make(admin, "Seller Seven", "Seller", 108, "Missed call", assigned_to=admin)
	make(admin, "Partner Lead One", "Buyer", 109, "Channel partner", assigned_to=partner)
	make(admin, "Partner Lead Two", "Investor", 110, "Channel partner", assigned_to=partner)

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
	_seed_twin_clients(admin, agent_one)
	_seed_lead_sources(admin)
	_seed_pipeline_stages()
	_seed_call_outcomes(admin, agent_one)
	_seed_users(admin)
	_seed_dormant_lead(admin, agent_one)
	_seed_queue_lead(admin, agent_one)
	_seed_bought_list(admin)
	_seed_support_grants(admin)
	_seed_telephony(admin)
	_seed_click_to_call_agent(admin, agent_one)
	_seed_calling_rules(admin, agent_one)
	_seed_call_reports_regression()
	_seed_control_site()
	_seed_setup_wizard(admin)
	_seed_sales_teams(admin, agent_one, agent_two, agent_three)
	_seed_follow_ups(agent_one)
	_seed_notifications(agent_one)
	_seed_site_visits(agent_one, agent_two)
	_seed_partner_firms(admin)
	_seed_partner_registrations(admin)
	_seed_inventory(admin, agent_one)
	_seed_inbound_opt_in()

	# bench execute is not a request, and the regression site is read by another process.
	frappe.db.commit()  # nosemgrep
	return _regression_summary()


def _seed_call_reports_regression():
	"""Seven calls on the regression leads (SOS-P2-11), through the fake provider and the production call
	functions, so the call reports have something to add up. Safe to run again: leads that already have a
	Call Log are left alone."""
	titles = {
		"soon": "Buyer Two",
		"months": "Queue Application",
		"forever": "Buyer One",
		"unknown": "Investor Four",
		"opted": "Buyer Three",
		"dnd": "DND Listed",
	}
	leads = {}
	for key, title in titles.items():
		client = frappe.db.get_value("Client", {"client_name": f"{REGRESSION_PREFIX}{title}"}, "name")
		lead = frappe.db.get_value("Lead", {"client": client}, "name") if client else None
		if not lead:
			return
		leads[key] = lead
	if frappe.db.exists("Call Log", {"lead": ["in", list(leads.values())]}):
		return
	place_report_calls(leads)


def _seed_bought_list(admin):
	"""Regression Bought One (Unknown) and Regression Bought Two (a do not call result of Yes, so Registered
	DND) from a bought list file (SOS-P1-12), made by the import API as the Company Admin. The file lists
	Two twice under different names to show the merge. Safe to run again."""
	from sellos.crm import api as crm

	if frappe.db.exists("Client", {"client_name": f"{REGRESSION_PREFIX}Bought One"}):
		return
	one, two = phones.in_mobile(1301), phones.in_mobile(1302)
	text = "\n".join(
		(
			"Name,Mobile,Email,City,DND Status",
			f"{REGRESSION_PREFIX}Bought One,{one},regression_bought_one@example.com,Pune,",
			f"{REGRESSION_PREFIX}Bought Two,{two},regression_bought_two@example.com,Thane,Yes",
			f"{REGRESSION_PREFIX}Bought Two Again,{two},,,",
		)
	)
	with _as_user(admin):
		crm.import_bought_list(text, list_name="Regression bought list")


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


def _seed_twin_clients(admin, agent_one):
	"""One person entered twice (SOS-P1-16), through the CRM API as the Company Admin.

	Twin A and Twin B each have a lead and an activity and are given the same email. Safe to run
	again: when Twin A is already there nothing is made.
	"""
	from sellos.crm import api as crm

	if frappe.db.exists("Client", {"client_name": f"{REGRESSION_PREFIX}Twin A"}):
		return
	with _as_user(admin):
		for letter, seed, source in (("A", 111, "Website"), ("B", 112, "Walk in")):
			client = crm.save_client(
				values={
					"client_name": f"{REGRESSION_PREFIX}Twin {letter}",
					"client_type": "Buyer",
					"email": "regression_twin@example.com",
					"city": "Mumbai",
					"phone": phones.in_mobile(seed),
				}
			)
			lead = crm.save_lead(
				values={"client": client["name"], "source": source, "assigned_to": agent_one}
			)
			crm.add_activity(lead["lead"]["name"], "Call", f"Regression twin {letter} first call")


def _seed_lead_sources(admin):
	"""The lead sources (SOS-P1-20), through the CRM API as the Company Admin. Safe to run again.

	Regression Roadshow is a source the company added and Regression Old Hoarding one it disabled.
	Regression Buyer Three came through the Roadshow, under the campaign Diwali 2026 hoardings.
	"""
	from sellos.crm import api as crm

	with _as_user(admin):
		have = {row["name"] for row in crm.list_lead_sources(include_disabled=1)["sources"]}
		if "Regression Roadshow" not in have:
			crm.save_lead_source(values={"source_name": "Regression Roadshow"})
		if "Regression Old Hoarding" not in have:
			crm.save_lead_source(values={"source_name": "Regression Old Hoarding"})
			crm.save_lead_source(name="Regression Old Hoarding", values={"enabled": 0})
		client = frappe.db.get_value("Client", {"client_name": f"{REGRESSION_PREFIX}Buyer Three"}, "name")
		lead = frappe.db.get_value("Lead", {"client": client}, "name") if client else None
		if lead:
			crm.save_lead(
				name=lead, values={"source": "Regression Roadshow", "campaign": "Diwali 2026 hoardings"}
			)


def _seed_follow_ups(agent_one):
	"""An overdue follow up on Buyer Two and one due in ten minutes on Buyer One (SOS-P1-22), saved through
	the task API by their agent. Safe to run again: a follow up that exists is left alone. The times are
	relative to the run, so a run later in the day finds them overdue."""
	from sellos.crm import api as crm

	plan = (
		("Buyer Two", "Regression chase the site visit", add_to_date(now_datetime(), hours=-2)),
		("Buyer One", "Regression ring back soon", add_to_date(now_datetime(), minutes=10)),
	)
	for who, title, when in plan:
		lead = frappe.db.get_value("Lead", {"lead_title": ["like", f"{REGRESSION_PREFIX}{who}%"]}, "name")
		if not lead or frappe.db.exists("Lead Task", {"lead": lead, "title": title}):
			continue
		with _as_user(agent_one):
			crm.save_task(
				values={
					"lead": lead,
					"title": title,
					"due_at": when,
					"status": "Open",
					"assigned_to": agent_one,
				}
			)


def _seed_notifications(agent_one):
	"""A site visit tomorrow on Buyer One, scheduled by its agent through the visit API, and one run of the
	scheduler's notification functions (SOS-P1-23). Safe to run again: a visit that exists is left alone and
	a notification is never made twice."""
	from sellos.crm import api as crm
	from sellos.crm import notifications

	lead = frappe.db.get_value("Lead", {"lead_title": ["like", f"{REGRESSION_PREFIX}Buyer One%"]}, "name")
	project = f"{REGRESSION_PREFIX}Tomorrow Heights"
	if lead and not frappe.db.exists("Site Visit", {"lead": lead, "project_name": project}):
		stage = frappe.db.get_value("Lead", lead, "stage")
		with _as_user(agent_one):
			crm.save_site_visit(
				values={
					"lead": lead,
					"project_name": project,
					"visit_datetime": add_to_date(get_datetime(add_days(today(), 1)), hours=11),
					"status": "Scheduled",
				}
			)
			# Booking moves a lead to Site visit booked (SOS-P1-25). Buyer One stays where the stage flows
			# (SOS-P1-07) expect it, so the agent moves it back through the same API.
			if frappe.db.get_value("Lead", lead, "stage") != stage:
				crm.move_lead_stage(lead, stage)
	notifications.notify_follow_ups()
	notifications.notify_site_visits()


def _seed_site_visits(agent_one, agent_two):
	"""Tomorrow's site visits (SOS-P1-25), booked by their agents through the visit API: Regression Skyline
	Walkthrough on Regression Buyer Two (the gate agent's, confirmed by the agent after the call) and
	Regression Lakeside Tour on Regression Buyer Three (Regression Agent Two's). With Regression Tomorrow
	Heights (Not confirmed) on Buyer One, the gate agent's list of tomorrow's visits holds two and the
	Sales Manager's holds three. Safe to run again: a visit that exists is left alone."""
	from sellos.crm import api as crm

	plan = (
		(agent_one, "Buyer Two", "Regression Skyline Walkthrough", 15, "Confirmed"),
		(agent_two, "Buyer Three", "Regression Lakeside Tour", 16, None),
	)
	for agent, who, project, hour, confirmation in plan:
		lead = frappe.db.get_value("Lead", {"lead_title": ["like", f"{REGRESSION_PREFIX}{who}%"]}, "name")
		if not lead or frappe.db.exists("Site Visit", {"lead": lead, "project_name": project}):
			continue
		with _as_user(agent):
			visit = crm.save_site_visit(
				values={
					"lead": lead,
					"project_name": project,
					"visit_datetime": add_to_date(get_datetime(add_days(today(), 1)), hours=hour),
				}
			)
			if confirmation:
				crm.confirm_site_visit(visit["name"], confirmation)
	_seed_today_visit(agent_one)


def _seed_today_visit(agent_one):
	"""Regression Noon Walkthrough, a site visit at noon today on Regression Buyer Two (SOS-P1-26), booked by
	its agent through the visit API so that Today has a visit for today. Buyer Two is already on Site visit
	booked, so its stage does not move. Safe to run again: a visit that exists is left alone."""
	from sellos.crm import api as crm

	lead = frappe.db.get_value("Lead", {"lead_title": ["like", f"{REGRESSION_PREFIX}Buyer Two%"]}, "name")
	project = "Regression Noon Walkthrough"
	if not lead or frappe.db.exists("Site Visit", {"lead": lead, "project_name": project}):
		return
	with _as_user(agent_one):
		crm.save_site_visit(
			values={
				"lead": lead,
				"project_name": project,
				"visit_datetime": add_to_date(get_datetime(today()), hours=12),
			}
		)


def _seed_dormant_lead(admin, agent_one):
	"""Regression Dormant Eight (SOS-P1-24): a lead made through the API and then dated 30 days back, so
	it has had no activity for longer than the untouched period. Safe to run again."""
	from frappe.utils import add_days, now_datetime

	from sellos.crm import api as crm

	title = f"{REGRESSION_PREFIX}Dormant Eight"
	if frappe.db.exists("Client", {"client_name": title}):
		return
	with _as_user(admin):
		client = crm.save_client(
			values={
				"client_name": title,
				"client_type": "Buyer",
				"email": "regression_dormant_eight@example.com",
				"city": "Mumbai",
				"phone": phones.in_mobile(111),
			}
		)
		lead = crm.save_lead(
			values={
				"client": client["name"],
				"source": "Referral",
				"assigned_to": agent_one,
				"budget_to": 7000000,
			}
		)["lead"]["name"]
	frappe.db.set_value("Lead", lead, "creation", add_days(now_datetime(), -30), update_modified=False)


def _seed_queue_lead(admin, agent_one):
	"""Regression Queue Application (SOS-P2-09): a lead with a live Application consent, which lapses in
	three months, so the caller queue has lapsing leads with different expiries (this one after Buyer Two's
	Inquiry, which lapses in seven days). Made through the API. Safe to run again."""
	from sellos.crm import api as crm

	title = f"{REGRESSION_PREFIX}Queue Application"
	if frappe.db.exists("Client", {"client_name": title}):
		return
	with _as_user(admin):
		client = crm.save_client(
			values={"client_name": title, "client_type": "Buyer", "phone": phones.in_mobile(131)}
		)
		lead = crm.save_lead(
			values={"client": client["name"], "source": "Website", "assigned_to": agent_one}
		)["lead"]["name"]
	with _as_user(agent_one):
		crm.record_consent(lead, "Application", "https://example.com/regression/application-queue")


def _seed_pipeline_stages():
	"""Move some regression leads along the buyer pipeline (SOS-P1-07), through the production API as
	each lead's own agent. A lead that has left the first stage is left alone, so it is safe to run again."""
	from sellos.crm import api as crm

	first = pipeline.first_stage()
	plan = {
		"Buyer One": ["Contacted", "Qualified"],
		"Buyer Two": ["Site visit booked"],
		"Buyer Three": ["Contacted"],
		"Investor Four": ["Contacted"],
		"NRI Five": ["Nurture"],
	}
	for title, stages in plan.items():
		lead = frappe.db.get_value(
			"Lead",
			{"lead_title": ["like", f"{REGRESSION_PREFIX}{title}%"]},
			["name", "assigned_to", "stage"],
			as_dict=True,
		)
		if not lead or lead.stage != first:
			continue
		with _as_user(lead.assigned_to):
			for stage in stages:
				crm.move_lead_stage(lead.name, stage)


def _seed_call_outcomes(admin, agent_one):
	"""The call outcome and lost reason lists and one call logged by hand (SOS-P1-21), through the CRM
	API: the Company Admin adds an outcome and a lost reason, and the first agent logs a call on
	Regression Buyer Two. Safe to run again: each is looked up first."""
	from sellos.crm import api as crm
	from sellos.crm import call_outcomes

	call_outcomes.ensure_defaults()
	with _as_user(admin):
		have = {row["name"] for row in crm.list_call_outcomes(include_disabled=1)["outcomes"]}
		if "Regression Sent brochure" not in have:
			crm.save_call_outcome(
				values={
					"outcome_name": "Regression Sent brochure",
					"needs_follow_up": 1,
					"suggested_stage": "Contacted",
				}
			)
		have = {row["name"] for row in crm.list_lost_reasons(include_disabled=1)["lost_reasons"]}
		if "Regression Price too high" not in have:
			crm.save_lost_reason(values={"reason_name": "Regression Price too high"})
	client = frappe.db.get_value("Client", {"client_name": f"{REGRESSION_PREFIX}Buyer Two"}, "name")
	lead = frappe.db.get_value("Lead", {"client": client}, "name") if client else None
	if lead and not frappe.db.exists("Lead Activity", {"lead": lead, "outcome": "Busy"}):
		with _as_user(agent_one):
			crm.log_call(
				lead,
				"Busy",
				notes="Regression call, in a meeting",
				duration_seconds=120,
				follow_up_at=add_to_date(now_datetime(), days=1),
			)


def remove_gate_call_lists():
	"""Remove what the call outcome spec committed (tests only, SOS-P1-21): the outcomes named Gate Outcome
	and the lost reasons named Gate Reason. Run remove_seeded_leads first, so no call still names them."""
	outcomes = frappe.get_all("Call Outcome", filters={"name": ["like", "Gate Outcome %"]}, pluck="name")
	reasons = frappe.get_all("Lost Reason", filters={"name": ["like", "Gate Reason %"]}, pluck="name")
	for doctype, names in (("Call Outcome", outcomes), ("Lost Reason", reasons)):
		if names:
			frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ["in", names]})
			frappe.db.delete(doctype, {"name": ["in", names]})
	frappe.db.commit()  # nosemgrep
	return {"outcomes": len(outcomes), "lost_reasons": len(reasons)}


SEEDED_USERS = (
	("regression_new_agent@example.com", "Regression New Agent", 301),
	("regression_agent_no_mobile@example.com", "Regression Agent No Mobile", None),
	("regression_former_agent@example.com", "Regression Former Agent", 302),
)


def _seed_users(admin):
	"""Three invited users, one of them deactivated with work waiting (SOS-P1-17), through the production
	methods as the Company Admin. The invitation mail is switched off, so no mail is ever sent."""
	from unittest.mock import patch

	from sellos.access import users
	from sellos.crm import api as crm

	with _as_user(admin), patch.object(users, "mail_ready", return_value=False):
		for email, first_name, seed in SEEDED_USERS:
			if not frappe.db.exists("User", email):
				users.invite_user(
					email, first_name, "SellOS Agent", "", phones.in_mobile(seed) if seed else ""
				)
		former = SEEDED_USERS[2][0]
		handover = SEEDED_USERS[1][0]  # SOS-P1-19: a leaving agent's work goes to another agent
		if not frappe.db.exists("Client", {"client_name": f"{REGRESSION_PREFIX}Former Agent Buyer"}):
			client = crm.save_client(
				values={
					"client_name": f"{REGRESSION_PREFIX}Former Agent Buyer",
					"client_type": "Buyer",
					"phone": phones.in_mobile(303),
				}
			)
			lead = crm.save_lead(
				values={"client": client["name"], "source": "Website", "assigned_to": former}
			)
			crm.save_task(
				values={
					"lead": lead["lead"]["name"],
					"title": f"{REGRESSION_PREFIX}Call the buyer back",
					"due_date": add_days(today(), 1),
					"assigned_to": former,
				}
			)
		if frappe.db.get_value("User", former, "enabled"):
			users.deactivate_user(former, reassign_to=handover)


def seed_user_work(email):
	"""Give a user one open lead and one open task, for the users spec (tests only, SOS-P1-17). The client
	is named Gate Consent Users, so remove_seeded_leads removes the lead and the task afterwards."""
	from sellos.crm import api as crm

	_test_users()
	tag = frappe.generate_hash(length=6)
	with _as_user(TEST_USERS["company_admin"]["email"]):
		client = crm.save_client(
			values={
				"client_name": f"Gate Consent Users {tag}",
				"client_type": "Buyer",
				"phone": phones.in_mobile(304),
			}
		)
		lead = crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": email})
		task = crm.save_task(
			values={
				"lead": lead["lead"]["name"],
				"title": "Gate users task",
				"due_date": add_days(today(), 2),
				"assigned_to": email,
			}
		)
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"lead": lead["lead"]["name"], "task": task["name"]}


GATE_USER_PREFIX = "gate_invited_"


def gate_user_email(tag):
	return {"email": f"{GATE_USER_PREFIX}{tag}@example.com"}


def set_gate_user_password(email):
	"""Set the password of a user the users spec invited, as the invitation link would (tests only,
	SOS-P1-17: the spec has no mail to read the link from). Returns {"user", "password"}."""
	from frappe.utils.password import update_password

	if not email.startswith(GATE_USER_PREFIX) or not frappe.db.exists("User", email):
		raise ValueError("Only a user the users spec invited.")
	update_password(email, PASSWORD)
	frappe.db.commit()  # the browser signs in from another process  # nosemgrep
	return {"user": email, "password": PASSWORD}


def remove_gate_users():
	"""Remove the users the users spec invited (email starting gate_invited_), with their contacts,
	sessions and history (tests only, SOS-P1-17). Run remove_seeded_leads first. The app never deletes a user."""
	emails = frappe.get_all("User", filters={"name": ["like", f"{GATE_USER_PREFIX}%"]}, pluck="name")
	for email in emails:
		frappe.db.delete("Sessions", {"user": email})
		frappe.db.delete("Version", {"ref_doctype": "User", "docname": email})
		for contact in frappe.get_all("Contact", filters={"email_id": email}, pluck="name"):
			frappe.delete_doc("Contact", contact, force=True, ignore_permissions=True)
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep
	return {"users": len(emails)}


def _seed_support_grants(admin):
	"""Two support grants, through the production API (SOS-P1-13): one ended early, one still active."""
	from sellos.access import support

	support_user = TEST_USERS["platform_admin"]["email"]
	with _as_user(admin):
		ended = support.grant_support_access(support_user, 60, "Regression help with an import")
		support.revoke_support_access(ended["name"])
		support.grant_support_access(support_user, 120, "Regression walkthrough of the leads report")


def _seed_telephony(admin):
	"""The Plivo India account saved once (SOS-P2-01), through the production API, with the fake provider.

	The keys are fake ones that the fake provider accepts, so Test connection works on the regression
	site without the real provider. Safe to run again: an account that is already saved is left alone.
	"""
	from sellos.telephony import settings

	use_fake_telephony_provider()
	with _as_user(admin):
		if settings.get_telephony_settings()["configured"]:
			return
		settings.save_telephony_settings(
			auth_id=TELEPHONY_FAKE_ID,
			auth_token=TELEPHONY_FAKE_TOKEN,
			phone_number=landline_022(TELEPHONY_SEED),
		)


CLICK_TO_CALL_SEED = 2301


def _seed_click_to_call_agent(admin, agent):
	"""The agent's Indian mobile number (SOS-P2-07), saved by the Company Admin through the users API, so
	click to call can ring them first. Safe to run again: a number already saved is left alone."""
	from sellos.access import users

	if frappe.db.get_value("User", agent, "mobile_no"):
		return
	with _as_user(admin):
		users.save_user(agent, {"mobile_no": phones.in_mobile(CLICK_TO_CALL_SEED)})


CALLING_RULES_SEED = 2401
DND_QUEUE_SEED = 84  # the number of the caller queue's Unknown lead, made by seed_caller_queue


def _seed_calling_rules(admin, agent_one):
	"""Calling hours (saved, switched off) and a do not call list with one number (SOS-P2-10), through the
	Company Admin's methods. Regression DND Listed is a lead of the gate agent with that number, so it is
	Registered DND. Safe to run again: a lead that exists is left alone."""
	from sellos.crm import api as crm
	from sellos.telephony import dnd, hours

	title = f"{REGRESSION_PREFIX}DND Listed"
	if frappe.db.exists("Client", {"client_name": title}):
		return
	with _as_user(admin):
		hours.save_calling_hours(0, "09:00", "21:00", "Mon,Tue,Wed,Thu,Fri,Sat")
		client = crm.save_client(
			values={
				"client_name": title,
				"client_type": "Buyer",
				"phone": phones.in_mobile(CALLING_RULES_SEED),
			}
		)
		crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": agent_one})
		dnd.import_do_not_call_list(phones.in_mobile(CALLING_RULES_SEED), "Regression list")


def seed_calling_rules():
	"""What the calling rules spec needs (SOS-P2-10): everything click to call needs, plus a calling window
	that is closed right now (so a spec can save it and see the refusal) and the number of the Unknown lead
	of the caller queue, which the spec imports as a do not call list. remove_calling_rules undoes it."""
	seed = seed_click_to_call()
	closed = ("14:00", "20:00") if frappe.utils.now_datetime().hour < 12 else ("01:00", "05:00")
	return {
		**seed,
		"closed_start": closed[0],
		"closed_end": closed[1],
		"dnd_number": phones.in_mobile(DND_QUEUE_SEED),
	}


def remove_calling_rules():
	"""Undo seed_calling_rules (tests only): the do not call list, the calling hours and click to call's data."""
	frappe.db.delete("Do Not Call Number", {"number": phones.in_mobile(DND_QUEUE_SEED)})
	return remove_click_to_call()


def seed_click_to_call():
	"""What the click to call spec needs (SOS-P2-07): the fake provider on, the Plivo account saved with fake
	keys and a 022 number, the test agent's Indian mobile number, and the caller queue's six leads (one for
	each consent case, SOS-P2-09) owned by the test agent. Returns the queue seed and the agent's number
	(the agent's own, which they may see). remove_click_to_call undoes it."""
	from sellos.access import users
	from sellos.telephony import settings

	use_fake_telephony_provider()
	seed = seed_caller_queue()
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	with _as_user(admin):
		settings.save_telephony_settings(
			auth_id=TELEPHONY_FAKE_ID,
			auth_token=TELEPHONY_FAKE_TOKEN,
			phone_number=landline_022(TELEPHONY_SEED),
		)
		users.save_user(agent, {"mobile_no": phones.in_mobile(CLICK_TO_CALL_SEED)})
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return seed


def set_click_to_call_agent_mobile(abroad=True):
	"""Give the test agent a mobile number outside India (or an Indian one again), so the spec can check the
	clear error. The users API refuses a foreign number, so this goes to the field (tests only)."""
	agent = TEST_USERS["agent"]["email"]
	number = phones.au_mobile(CLICK_TO_CALL_SEED) if abroad else phones.in_mobile(CLICK_TO_CALL_SEED)
	frappe.db.set_value("User", agent, "mobile_no", number)
	frappe.db.commit()  # nosemgrep
	return {"abroad": bool(abroad)}


def play_click_to_call(step):
	"""Play one step of the fake provider's call for the test agent's latest click to call (SOS-P2-07).

	Steps: "agent_answers" (the agent's phone is answered, so the lead is rung), "lead_answers" and
	"hangup" (the lead's leg ends after 42 seconds). Each goes through the same function the Plivo webhook
	uses, so the Call Log moves as it would in a real call. Returns the call's status as the agent sees it."""
	from sellos.telephony import click_to_call, webhook
	from sellos.telephony.base import CallEvent

	agent = TEST_USERS["agent"]["email"]
	log = frappe.get_all(
		"Call Log", filters={"agent": agent}, order_by="creation desc", limit=1, pluck="name"
	)[0]
	call_id, lead_leg = frappe.db.get_value("Call Log", log, ["call_id", "lead_call_id"])
	events = {
		"agent_answers": CallEvent(call_id, "in-progress"),
		"lead_answers": CallEvent(lead_leg or "", "in-progress"),
		"hangup": CallEvent(lead_leg or "", "completed", duration=42),
	}
	webhook.apply_plivo_event(events[step])
	frappe.db.commit()  # nosemgrep
	with _as_user(agent):
		return click_to_call.call_status(log)


def remove_click_to_call():
	"""Undo seed_click_to_call (tests only): the agent's Call Logs and Consent Checks, the telephony account,
	the agent's mobile number and the six leads. The app deletes none of them, so this goes to the tables."""
	agent = TEST_USERS["agent"]["email"]
	logs = frappe.get_all("Call Log", filters={"agent": agent}, pluck="name")
	if logs:
		frappe.db.delete("Consent Check", {"reference_doctype": "Call Log", "reference_name": ["in", logs]})
		frappe.db.delete("Version", {"ref_doctype": "Call Log", "docname": ["in", logs]})
		frappe.db.delete("Call Log", {"name": ["in", logs]})
	frappe.db.set_value("User", agent, "mobile_no", "")
	remove_telephony_settings()
	return remove_seeded_leads()


# SOS-P2-11: the calls the call reports are checked with. Each row is (lead key, purpose, state, seconds,
# cost in paise, days ago, who clicked). Cost and talk time are what the provider's last event says.
REPORT_CALL_PLAN = (
	("soon", "Service", "completed", 125, 300, 2, "agent"),
	("months", "Service", "completed", 61, 150, 3, "agent"),
	("forever", "Transactional", "completed", 30, 100, 5, "company_admin"),
	("unknown", "Service", "no-answer", 0, 0, 5, "agent"),
	("opted", "Transactional", "busy", 0, 0, 40, "agent"),
	("dnd", "Service", "completed", 600, 1000, 10, "company_admin"),
	("unknown", "Transactional", "failed", 0, 0, 1, "agent"),
)


def place_report_calls(leads, plan=REPORT_CALL_PLAN):
	"""Place the plan's calls through the fake provider and the production call functions (SOS-P2-11), and
	return one dict per call: its log, lead key, purpose, state, seconds, rupees, day and who clicked.

	`leads` maps each lead key to a lead name. The fake provider takes the call, the provider's last event
	(through apply_event, as the webhook does) sets its state, seconds and cost, and the call's day and
	agent are set on the log, because a fake call starts now and nobody clicked. Does not commit."""
	from sellos.telephony import call_log, settings
	from sellos.telephony.base import CallEvent

	_test_users()
	admin = TEST_USERS["company_admin"]["email"]
	frappe.db.set_single_value("Telephony Settings", "provider", "fake")
	with _as_user(admin):
		settings.save_telephony_settings(
			auth_id=TELEPHONY_FAKE_ID,
			auth_token=TELEPHONY_FAKE_TOKEN,
			phone_number=landline_022(TELEPHONY_SEED),
		)
	made = []
	for key, purpose, state, seconds, paise, days_ago, who in plan:
		log = call_log.place_logged_call(leads[key], purpose)["log"]
		call_id = frappe.db.get_value("Call Log", log, "call_id")
		call_log.apply_event(CallEvent(call_id, state, duration=seconds), cost=paise, cost_unit="paise")
		started = add_days(now_datetime(), -days_ago)
		agent = TEST_USERS[who]["email"]
		frappe.db.set_value("Call Log", log, {"started_on": started, "agent": agent})
		made.append(
			{
				"log": log,
				"lead_key": key,
				"purpose": purpose,
				"state": state,
				"seconds": seconds,
				"rupees": paise / 100,
				"day": str(get_datetime(started).date()),
				"agent": agent,
			}
		)
	return made


def call_log_totals(from_date, to_date):
	"""What the Call Log table itself holds for the two days (SOS-P2-11), read with SQL that shares no code
	with the report, so a spec can check the report against it: calls, connected, seconds and rupees."""
	row = frappe.db.sql(
		"""select count(*), coalesce(sum(state = 'completed' and duration > 0), 0),
			coalesce(sum(duration), 0), coalesce(sum(cost_rupees), 0)
		from `tabCall Log` where date(started_on) between %s and %s""",
		(from_date, to_date),
	)[0]
	return {"calls": int(row[0]), "connected": int(row[1]), "seconds": int(row[2]), "rupees": float(row[3])}


def seed_call_reports():
	"""What the call reports spec needs (SOS-P2-11): the caller queue's six leads (one for each consent
	case), seven calls on them placed through the fake provider (REPORT_CALL_PLAN), and the date range that
	holds all but the oldest. Returns the calls, the range and what the Call Log holds for it.
	remove_call_reports undoes it."""
	seed = seed_caller_queue()
	calls = place_report_calls(seed["leads"])
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	start, end = str(add_days(today(), -12)), str(today())
	return {**seed, "calls": calls, "from_date": start, "to_date": end, "totals": call_log_totals(start, end)}


def remove_call_reports():
	"""Undo seed_call_reports (tests only): the calls of the six leads, their Consent Checks, the telephony
	account and the leads. The app deletes none of them, so this goes to the tables."""
	clients = frappe.get_all("Client", filters={"client_name": ["like", "Gate Consent %"]}, pluck="name")
	leads = frappe.get_all("Lead", filters={"client": ["in", clients]}, pluck="name") if clients else []
	logs = frappe.get_all("Call Log", filters={"lead": ["in", leads]}, pluck="name") if leads else []
	if logs:
		frappe.db.delete("Consent Check", {"reference_doctype": "Call Log", "reference_name": ["in", logs]})
		frappe.db.delete("Version", {"ref_doctype": "Call Log", "docname": ["in", logs]})
		frappe.db.delete("Call Log", {"name": ["in", logs]})
	remove_telephony_settings()
	return remove_seeded_leads()


def _seed_setup_wizard(admin):
	"""A setup wizard left half way (SOS-P1-03): profile, colours and stages saved, users not yet.

	Run through the production API as the Company Admin, so the wizard opens on its last step. It keeps
	the company's own name and the SellOS brand colour, so the rest of the app looks the same.
	"""
	from sellos.config import setup_wizard

	done = frappe.db.get_single_value("SellOS Settings", "setup_steps_done") or ""
	if "stages" in done.split(",") or setup_wizard.is_setup_complete():
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


def _seed_sales_teams(admin, agent_one, agent_two, agent_three):
	"""Two sales teams (SOS-P1-18), made through the team API as the Company Admin. Regression Team North is
	run by the Sales Manager test user with the test agent and Regression Agent Two, so that manager sees
	their leads and not Regression Agent Three's. Regression Team South has its own manager and agent three.
	Safe to run again: a team that exists is left alone."""
	from sellos.access import teams

	_test_users()
	manager_two = {
		"email": "regression_manager_two@example.com",
		"first_name": "Regression Manager Two",
		"roles": ["SellOS Sales Manager"],
		"desk": False,
	}
	_ensure_user(manager_two)
	with _as_user(admin):
		for name, manager, members in (
			("Regression Team North", TEST_USERS["sales_manager"]["email"], [agent_one, agent_two]),
			("Regression Team South", manager_two["email"], [agent_three]),
		):
			if not frappe.db.exists("Sales Team", name):
				teams.save_team(values={"team_name": name, "manager": manager, "members": members})


GATE_TEAM_USERS = {
	"manager": {
		"email": "gate_team_manager@example.com",
		"first_name": "Gate Team Manager",
		"roles": ["SellOS Sales Manager"],
		"desk": False,
	},
	"agent": {
		"email": "gate_team_agent@example.com",
		"first_name": "Gate Team Agent",
		"roles": ["SellOS Agent"],
		"desk": False,
	},
	"spare": {
		"email": "gate_team_spare@example.com",
		"first_name": "Gate Team Spare",
		"roles": ["SellOS Agent"],
		"desk": False,
	},
}


def seed_sales_teams():
	"""Two teams and a lead in each, for the sales teams spec (SOS-P1-18), made through the team and lead
	APIs as the Company Admin. Team A is the Sales Manager test user with the test agent, who owns
	{"own"}. Team B is Gate Team Manager with Gate Team Agent, who owns {"other"}. Gate Team Spare is an agent
	in no team. Return the client names the lead rows show and the people's names. Run
	remove_sales_teams after: a team left behind would put the test agent in two teams for the backend tests."""
	from sellos.access import teams
	from sellos.crm import api as crm

	_test_users()
	for spec in GATE_TEAM_USERS.values():
		_ensure_user(spec)
	admin = TEST_USERS["company_admin"]["email"]
	tag = frappe.generate_hash(length=6)
	made = {}
	with _as_user(admin):
		for key, assignee, seed, team_name, manager in (
			("own", TEST_USERS["agent"]["email"], 41, f"Gate Team A {tag}", TEST_USERS["sales_manager"]),
			(
				"other",
				GATE_TEAM_USERS["agent"]["email"],
				42,
				f"Gate Team B {tag}",
				GATE_TEAM_USERS["manager"],
			),
		):
			teams.save_team(
				values={"team_name": team_name, "manager": manager["email"], "members": [assignee]}
			)
			client_name = f"Gate Team Lead {key.title()} {tag}"
			client = crm.save_client(
				values={"client_name": client_name, "client_type": "Buyer", "phone": phones.in_mobile(seed)}
			)
			crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": assignee})
			made[key] = client_name
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {
		**made,
		"team_a": f"Gate Team A {tag}",
		"team_b": f"Gate Team B {tag}",
		"manager_name": TEST_USERS["sales_manager"]["first_name"],
		"other_manager_name": GATE_TEAM_USERS["manager"]["first_name"],
		"spare_name": GATE_TEAM_USERS["spare"]["first_name"],
		"agent_name": TEST_USERS["agent"]["first_name"],
		"other_agent_name": GATE_TEAM_USERS["agent"]["first_name"],
		"phone_forms": phones.forms(phones.in_mobile(41)),
	}


def remove_sales_teams():
	"""Remove what the sales teams spec committed (tests only, SOS-P1-18): the teams named Gate Team, their
	leads and the Gate Team users. The app never deletes a team's leads, so this goes to the tables."""
	remove_seeded_leads()
	teams = frappe.get_all("Sales Team", filters={"team_name": ["like", "Gate Team %"]}, pluck="name")
	for name in teams:
		frappe.db.delete("Version", {"ref_doctype": "Sales Team", "docname": name})
		frappe.delete_doc("Sales Team", name, force=True, ignore_permissions=True)
	for spec in GATE_TEAM_USERS.values():
		email = spec["email"]
		if frappe.db.exists("User", email):
			frappe.db.delete("Sessions", {"user": email})
			frappe.db.delete("Version", {"ref_doctype": "User", "docname": email})
			for contact in frappe.get_all("Contact", filters={"email_id": email}, pluck="name"):
				frappe.delete_doc("Contact", contact, force=True, ignore_permissions=True)
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep
	return {"teams": len(teams)}


GATE_TODAY_AGENT = {
	"email": "gate_today_agent@example.com",
	"first_name": "Gate Today Agent",
	"roles": ["SellOS Agent"],
	"desk": False,
}


def seed_today():
	"""What the Today spec needs (SOS-P1-26), made through the lead, task and site visit APIs. The test
	agent owns Gate Today Mine New (stage New), Gate Today Mine Busy (a follow up two hours ago and one
	with only today's day, a visit today at noon and one tomorrow at ten) and Gate Today Mine Later (a
	follow up tomorrow, which is not on Today). Gate Today Agent, in the same team Gate Today Team as the
	test Sales Manager, owns Gate Today Theirs (a follow up due today and a visit tomorrow) and Gate Today Theirs New (stage New).
	The Company Admin owns Gate Today Admin (stage New), whom neither sees. Return the client names, the
	spellings of the agent's first full number and the people's names. Run remove_today after: a team
	left behind would put the test agent in two teams for the backend tests."""
	from sellos.access import teams
	from sellos.crm import api as crm

	_test_users()
	_ensure_user(GATE_TODAY_AGENT)
	admin = TEST_USERS["company_admin"]["email"]
	agent = TEST_USERS["agent"]["email"]
	other = GATE_TODAY_AGENT["email"]
	tag = frappe.generate_hash(length=6)
	noon = add_to_date(get_datetime(today()), hours=12)
	tomorrow_ten = add_to_date(get_datetime(add_days(today(), 1)), hours=10)
	names, leads = {}, {}
	with _as_user(admin):
		teams.save_team(
			values={
				"team_name": f"Gate Today Team {tag}",
				"manager": TEST_USERS["sales_manager"]["email"],
				"members": [agent, other],
			}
		)
		for key, owner, seed, stage in (
			("mine_new", agent, 61, None),
			("mine_busy", agent, 62, "Contacted"),
			("mine_later", agent, 63, "Contacted"),
			("theirs", other, 64, "Contacted"),
			("theirs_new", other, 66, None),
			("admin", admin, 65, None),
		):
			client_name = f"Gate Today {key.replace('_', ' ').title()} {tag}"
			client = crm.save_client(
				values={"client_name": client_name, "client_type": "Buyer", "phone": phones.in_mobile(seed)}
			)
			lead = crm.save_lead(
				values={"client": client["name"], "source": "Website", "assigned_to": owner}
			)["lead"]["name"]
			if stage:
				crm.move_lead_stage(lead, stage)
			names[key], leads[key] = client_name, lead
		for key, title, owner, values in (
			(
				"mine_busy",
				"Gate Today overdue ring",
				agent,
				{"due_at": add_to_date(now_datetime(), hours=-2)},
			),
			("mine_busy", "Gate Today day only", agent, {"due_date": today()}),
			("mine_later", "Gate Today next week", agent, {"due_date": add_days(today(), 7)}),
			("theirs", "Gate Today team ring", other, {"due_date": today()}),
		):
			crm.save_task(
				values={"lead": leads[key], "title": title, "assigned_to": owner, "status": "Open", **values}
			)
		for key, owner, project, when in (
			("mine_busy", agent, "Gate Today Noon Tower", noon),
			("mine_busy", agent, "Gate Today Tomorrow Tower", tomorrow_ten),
			("theirs", other, "Gate Today Team Tower", tomorrow_ten),
		):
			crm.save_site_visit(
				values={"lead": leads[key], "project_name": project, "visit_datetime": when, "agent": owner}
			)
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {
		**names,
		"leads": leads,
		"agent_name": TEST_USERS["agent"]["first_name"],
		"other_agent_name": GATE_TODAY_AGENT["first_name"],
		"phone_forms": phones.forms(phones.in_mobile(61)),
		"overdue_forms": phones.forms(phones.in_mobile(62)),
	}


def remove_today():
	"""Remove what the Today spec committed (tests only, SOS-P1-26): the Gate Today leads, team and agent.
	The app never deletes a lead or a team, so this goes to the tables."""
	remove_seeded_leads()
	for name in frappe.get_all(
		"Sales Team", filters={"team_name": ["like", "Gate Today Team %"]}, pluck="name"
	):
		frappe.db.delete("Version", {"ref_doctype": "Sales Team", "docname": name})
		frappe.delete_doc("Sales Team", name, force=True, ignore_permissions=True)
	email = GATE_TODAY_AGENT["email"]
	if frappe.db.exists("User", email):
		frappe.db.delete("Sessions", {"user": email})
		frappe.db.delete("App Notification", {"recipient": email})
		frappe.db.delete("Version", {"ref_doctype": "User", "docname": email})
		for contact in frappe.get_all("Contact", filters={"email_id": email}, pluck="name"):
			frappe.delete_doc("Contact", contact, force=True, ignore_permissions=True)
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep
	return {"removed": True}


GATE_ASSIGN_USERS = {
	"from": {
		"email": "gate_assign_from@example.com",
		"first_name": "Gate Assign From",
		"roles": ["SellOS Agent"],
		"desk": False,
	},
	"to": {
		"email": "gate_assign_to@example.com",
		"first_name": "Gate Assign To",
		"roles": ["SellOS Agent"],
		"desk": False,
	},
}


def seed_bulk_reassign():
	"""Three leads held by Gate Assign From, each with an open follow up and a future site visit, and Gate
	Assign To who will take them, for the bulk reassignment spec (SOS-P1-19). Made through the lead, task
	and site visit APIs as the Company Admin. Run remove_gate_assignment after."""
	from sellos.access import teams
	from sellos.crm import api as crm

	_test_users()
	for spec in GATE_ASSIGN_USERS.values():
		_ensure_user(spec)
	tag = frappe.generate_hash(length=6)
	holder = GATE_ASSIGN_USERS["from"]["email"]
	names = []
	team = "Gate Assign Team"
	with _as_user(TEST_USERS["company_admin"]["email"]):
		if not frappe.db.exists("Sales Team", team):
			teams.save_team(
				values={
					"team_name": team,
					"manager": TEST_USERS["sales_manager"]["email"],
					"members": [GATE_ASSIGN_USERS["to"]["email"]],
				}
			)
		for n in (1, 2, 3):
			name = f"Gate Assign Lead {n} {tag}"
			client = crm.save_client(
				values={"client_name": name, "client_type": "Buyer", "phone": phones.in_mobile(430 + n)}
			)
			lead = crm.save_lead(
				values={"client": client["name"], "source": "Website", "assigned_to": holder}
			)
			crm.save_task(
				values={
					"lead": lead["lead"]["name"],
					"title": f"Gate Assign task {n}",
					"due_date": add_days(today(), 2),
					"assigned_to": holder,
				}
			)
			crm.save_site_visit(
				values={
					"lead": lead["lead"]["name"],
					"project_name": "Gate Assign Tower",
					"visit_datetime": f"{add_days(today(), 5)} 10:00:00",
				}
			)
			names.append(name)
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {
		"leads": names,
		"team": team,
		"to_name": GATE_ASSIGN_USERS["to"]["first_name"],
		"holder": holder,
		"taker": GATE_ASSIGN_USERS["to"]["email"],
	}


def seed_import_sample():
	"""The file the bought list import spec uploads, and the one client already in SellOS it matches
	(SOS-P1-12). Gate Import Known has a Website lead made through the API. The file lists Gate Import
	Alpha twice (the second time with a spaced number), Gate Import Beta with a do not call result of
	Yes, Gate Import Known, and a row with no name. Numbers are generated. Run remove_seeded_leads after."""
	from sellos.crm import api as crm

	_test_users()
	alpha, beta, known = (phones.in_mobile(seed) for seed in (1310, 1311, 1312))
	spaced = f"{alpha[:3]} {alpha[3:8]} {alpha[8:]}"
	with _as_user(TEST_USERS["company_admin"]["email"]):
		client = crm.save_client(values={"client_name": "Gate Import Known", "phone": known})
		crm.save_lead(values={"client": client["name"], "source": "Website"})
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	rows = (
		"Name,Mobile,Email,City,DND Status",
		f"Gate Import Alpha,{alpha},gate_import_alpha@example.com,Pune,No",
		f"Gate Import Alpha Twin,{spaced},,Thane,",
		f"Gate Import Beta,{beta},,Nashik,Yes",
		f"Gate Import Known,{known},,Mumbai,",
		f",{beta},,,",
	)
	return {"csv": "\n".join(rows), "names": ["Gate Import Alpha", "Gate Import Beta", "Gate Import Known"]}


def import_state(names):
	"""What the import made, read back from the database (tests only, SOS-P1-12): for each client name, how
	many clients and leads it has, and its lead's source, consent status and whether it is archived or
	opted out."""
	state = {}
	for name in names:
		clients = frappe.get_all("Client", filters={"client_name": name}, pluck="name")
		leads = frappe.get_all(
			"Lead",
			filters={"client": ["in", clients or [""]]},
			fields=["source", "consent_status", "archived", "opted_out_on", "stage"],
		)
		state[name] = {
			"clients": len(clients),
			"leads": [
				{
					"source": lead.source,
					"consent_status": lead.consent_status,
					"blocked": bool(lead.archived or lead.opted_out_on),
				}
				for lead in leads
			],
		}
	return state


def assignment_state(names):
	"""Where the leads of these clients, and their follow ups and future visits, are (tests only,
	SOS-P1-19): the agent of each lead, and how many tasks and visits each agent holds."""
	clients = frappe.get_all("Client", filters={"client_name": ["in", names]}, pluck="name")
	leads = frappe.get_all(
		"Lead", filters={"client": ["in", clients or [""]]}, fields=["name", "lead_title", "assigned_to"]
	)
	ids = [lead.name for lead in leads] or [""]
	state = {"leads": {lead.lead_title.rsplit(" ", 1)[0]: lead.assigned_to for lead in leads}}
	for doctype, field in (("Lead Task", "assigned_to"), ("Site Visit", "agent")):
		rows = frappe.get_all(doctype, filters={"lead": ["in", ids]}, pluck=field)
		state[doctype] = {agent: rows.count(agent) for agent in set(rows)}
	state["log"] = frappe.get_all(
		"Lead Assignment", filters={"lead": ["in", ids], "method": "Bulk"}, pluck="to_agent"
	)
	return state


def remove_gate_assignment():
	"""Remove what the assignment specs committed (tests only, SOS-P1-19): the Gate Assign leads and users
	and the rules named Gate Assign. The app never deletes a lead, so this goes to the tables."""
	remove_seeded_leads()
	for name in frappe.get_all(
		"Lead Assignment Rule", filters={"rule_name": ["like", "Gate Assign %"]}, pluck="name"
	):
		frappe.db.delete("Version", {"ref_doctype": "Lead Assignment Rule", "docname": name})
		frappe.delete_doc("Lead Assignment Rule", name, force=True, ignore_permissions=True)
	for name in frappe.get_all("Sales Team", filters={"team_name": "Gate Assign Team"}, pluck="name"):
		frappe.db.delete("Version", {"ref_doctype": "Sales Team", "docname": name})
		frappe.delete_doc("Sales Team", name, force=True, ignore_permissions=True)
	for spec in GATE_ASSIGN_USERS.values():
		email = spec["email"]
		if frappe.db.exists("User", email):
			frappe.db.delete("Sessions", {"user": email})
			frappe.db.delete("App Notification", {"recipient": email})
			frappe.db.delete("Version", {"ref_doctype": "User", "docname": email})
			for contact in frappe.get_all("Contact", filters={"email_id": email}, pluck="name"):
				frappe.delete_doc("Contact", contact, force=True, ignore_permissions=True)
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep
	return {"removed": True}


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


def site_date(days=0, at=None):
	"""A date of the site, from the server's own clock and time zone, never the browser's (SOS-LOOP: CI ran
	the browser in UTC while the site is in Asia/Kolkata, so "tomorrow" differed for hours of every day).
	`days` is added to the site's today. Returns "YYYY-MM-DD", or "YYYY-MM-DDTHH:MM" when `at` ("10:00")
	is given, the way a "datetime-local" box wants it. Returns {"date": ...} (bench execute prints JSON)."""
	day = add_days(today(), int(days))
	return {"date": f"{day}T{at}" if at else str(day)}


# --- Channel partner firms (SOS-P7-01) ------------------------------------------------------------

GATE_FIRM_PREFIX = "Gate Firm "
PARTNER_FIRM_SEEDS = (
	# firm name, contact email, how far it goes: invited, pending, approved or suspended
	("Regression Firm Invited", "regression_partner_invited@example.com", "invited"),
	("Regression Firm Pending", "regression_partner_pending@example.com", "pending"),
	("Regression Firm Approved", "regression_partner_approved@example.com", "approved"),
	("Regression Firm Suspended", "regression_partner_suspended@example.com", "suspended"),
)
PARTNER_PAN = "ABCPD1234E"
PARTNER_RERA = "A51800012345"


def _make_partner_firm(admin, firm_name, email, stage, phone_seed):
	"""Invite a firm as the Company Admin, let its contact person complete it, and take it as far as `stage`
	(invited, pending, approved or suspended), all through the production methods with mail switched off."""
	from unittest.mock import patch

	from sellos.access import partner_firms, users
	from sellos.tests.files import tiny_pdf_base64

	with _as_user(admin), patch.object(users, "mail_ready", return_value=False):
		code = partner_firms.invite_partner_firm(firm_name, f"{firm_name} Contact", email)["name"]
	if stage != "invited":
		with _as_user(email):
			partner_firms.submit_partner_details(
				{"phone": phones.in_mobile(phone_seed), "rera_number": PARTNER_RERA, "pan": PARTNER_PAN}
			)
			partner_firms.upload_my_agreement("signed_agreement.pdf", tiny_pdf_base64())
	with _as_user(admin):
		if stage in ("approved", "suspended"):
			partner_firms.approve_partner_firm(code)
		if stage == "suspended":
			partner_firms.suspend_partner_firm(code, "Regression: left the business")
	return code


def _seed_partner_firms(admin):
	"""The regression channel partner firms. Safe to run again: a firm that exists is left alone."""
	for seed, (firm_name, email, stage) in enumerate(PARTNER_FIRM_SEEDS, start=7010):
		if not frappe.db.exists("Channel Partner Firm", {"firm_name": firm_name}):
			_make_partner_firm(admin, firm_name, email, stage, seed)


def seed_gate_partner_firm(stage="pending"):
	"""For the partner firm spec (SOS-P7-01): make a firm whose contact person is the gate channel partner,
	through the production methods, and return {"name", "status"}. The firm is in the stage asked for:
	"pending" (details and agreement in), "approved" (SOS-P7-02, which needs an approved firm to register), or
	"invited"."""
	from sellos.access import partner_firms
	from sellos.tests.files import tiny_pdf_base64

	admin = TEST_USERS["company_admin"]["email"]
	partner = TEST_USERS["channel_partner"]["email"]
	_test_users()
	existing = frappe.db.get_value("Channel Partner Firm", {"contact_user": partner}, ["name", "status"])
	if existing:
		return {"name": existing[0], "status": existing[1]}
	with _as_user(admin):
		doc = frappe.get_doc(
			{
				"doctype": "Channel Partner Firm",
				"firm_name": f"{GATE_FIRM_PREFIX}Seeded",
				"contact_user": partner,
				"contact_person": "Gate Channel Partner",
				"email": partner,
			}
		).insert()
	if stage in ("pending", "approved"):
		with _as_user(partner):
			partner_firms.submit_partner_details(
				{"phone": phones.in_mobile(7001), "rera_number": PARTNER_RERA, "pan": PARTNER_PAN}
			)
			partner_firms.upload_my_agreement("gate_agreement.pdf", tiny_pdf_base64())
	if stage == "approved":
		with _as_user(admin):
			partner_firms.approve_partner_firm(doc.name)
	frappe.db.commit()  # nosemgrep
	return {"name": doc.name, "status": frappe.db.get_value("Channel Partner Firm", doc.name, "status")}


def gate_partner_firm_state(name):
	"""Read back a firm for the spec: its status, reason and status log (tests only, SOS-P7-01)."""
	doc = frappe.get_doc("Channel Partner Firm", name)
	return {
		"status": doc.status,
		"reason": doc.status_reason,
		"log": [(row.from_status, row.to_status, row.changed_by, row.reason) for row in doc.status_log],
		"pan": doc.pan,
		"agreement": doc.agreement,
	}


def remove_gate_partner_firms():
	"""Remove the firms and the logins the partner firm spec made, and the private agreement files (tests
	only, SOS-P7-01). The app never deletes a firm: this is the spec cleaning up after itself."""
	rows = frappe.get_all(
		"Channel Partner Firm",
		filters={"firm_name": ["like", f"{GATE_FIRM_PREFIX}%"]},
		fields=["name", "contact_user"],
	)
	for row in rows:
		for file in frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Channel Partner Firm", "attached_to_name": row.name},
			pluck="name",
		):
			frappe.delete_doc("File", file, force=True, ignore_permissions=True)
		frappe.db.delete("Partner Firm Status Change", {"parent": row.name})
		frappe.db.delete("Version", {"ref_doctype": "Channel Partner Firm", "docname": row.name})
		frappe.db.delete("Channel Partner Firm", {"name": row.name})
		if row.contact_user.startswith(GATE_USER_PREFIX):
			frappe.db.delete("Sessions", {"user": row.contact_user})
			for contact in frappe.get_all("Contact", filters={"email_id": row.contact_user}, pluck="name"):
				frappe.delete_doc("Contact", contact, force=True, ignore_permissions=True)
			frappe.delete_doc("User", row.contact_user, force=True, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep
	return {"firms": len(rows)}


# --- Partner registrations (SOS-P7-02) ------------------------------------------------------------

GATE_BUYER_PREFIX = "Gate Registration "
REGRESSION_REGISTRATIONS = (
	# buyer name, phone seed, what the Company Admin does: nothing, approve or reject
	("Regression Partner Buyer One", 7020, "wait"),
	("Regression Partner Buyer Two", 7021, "approve"),
	("Regression Partner Buyer Three", 7022, "reject"),
)


def _seed_partner_registrations(admin):
	"""Three buyers the Regression Firm Approved registered through register_buyer, as its contact person:
	one waiting for approval, one approved (protected) and one rejected with a reason. Safe to run again:
	a registration that exists is left alone."""
	from sellos.access import partner_registrations

	email = PARTNER_FIRM_SEEDS[2][1]  # Regression Firm Approved's contact person
	for name, seed, decision in REGRESSION_REGISTRATIONS:
		if frappe.db.exists("Partner Registration", {"buyer_name": name}):
			continue
		with _as_user(email):
			result = partner_registrations.register_buyer(
				name,
				phones.in_mobile(seed),
				"Regression Tower",
				"Seeded for the regression",
				1 if seed == 7021 else 0,
			)
		code = result["registration"]["name"]
		with _as_user(admin):
			if decision == "approve":
				partner_registrations.approve_partner_registration(code)
			elif decision == "reject":
				partner_registrations.reject_partner_registration(
					code, "Regression: the buyer is not interested"
				)


def seed_gate_partner_buyer():
	"""For the partner registration spec (SOS-P7-02): a buyer the company already has, made by the Company
	Admin, and the numbers the spec types. Returns {"existing_phone", "new_phone", "existing_name"}."""
	from sellos.crm import api as crm

	admin = TEST_USERS["company_admin"]["email"]
	_test_users()
	name = f"{GATE_BUYER_PREFIX}Existing"
	if not frappe.db.exists("Client", {"client_name": name}):
		with _as_user(admin):
			client = crm.save_client(
				values={"client_name": name, "client_type": "Buyer", "phone": phones.in_mobile(7401)}
			)
			crm.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": admin})
	frappe.db.commit()  # nosemgrep
	return {
		"existing_phone": phones.in_mobile(7401),
		"new_phone": phones.in_mobile(7402),
		"existing_name": name,
	}


def gate_partner_registration_state(buyer_name):
	"""Read back a registration for the spec (tests only, SOS-P7-02): its status, protection, log and lead."""
	doc = frappe.get_doc("Partner Registration", {"buyer_name": buyer_name})
	lead = frappe.get_doc("Lead", doc.lead)
	return {
		"name": doc.name,
		"status": doc.status,
		"protected_until": str(doc.protected_until or ""),
		"approved_on": str(doc.approved_on or ""),
		"log": [(row.from_status, row.to_status, row.changed_by) for row in doc.status_log],
		"lead_partner": lead.partner,
		"lead_source": lead.source,
		"consent_status": lead.consent_status,
		"count": frappe.db.count("Lead", {"client": doc.client}),
	}


def count_gate_partner_leads():
	"""How many leads and registrations the gate buyers have, so the spec can see that a refused buyer made none."""
	clients = frappe.get_all(
		"Client", filters={"client_name": ["like", f"{GATE_BUYER_PREFIX}%"]}, pluck="name"
	)
	return {
		"leads": frappe.db.count("Lead", {"client": ["in", clients]}) if clients else 0,
		"registrations": frappe.db.count(
			"Partner Registration", {"buyer_name": ["like", f"{GATE_BUYER_PREFIX}%"]}
		),
	}


def remove_gate_partner_registrations():
	"""Remove what the partner registration spec made (tests only, SOS-P7-02): the registrations, the leads
	and clients of the buyers named Gate Registration, their consent records and the partner's attempts.
	The app never deletes these, so this goes to the tables."""
	partner = TEST_USERS["channel_partner"]["email"]
	clients = frappe.get_all(
		"Client", filters={"client_name": ["like", f"{GATE_BUYER_PREFIX}%"]}, pluck="name"
	)
	leads = frappe.get_all("Lead", filters={"client": ["in", clients]}, pluck="name") if clients else []
	registrations = frappe.get_all(
		"Partner Registration", filters={"buyer_name": ["like", f"{GATE_BUYER_PREFIX}%"]}, pluck="name"
	)
	if registrations:
		frappe.db.delete("Partner Registration Change", {"parent": ["in", registrations]})
		frappe.db.delete("Version", {"ref_doctype": "Partner Registration", "docname": ["in", registrations]})
		frappe.db.delete("Partner Registration", {"name": ["in", registrations]})
	frappe.db.delete("Partner Registration Attempt", {"partner_user": partner})
	if leads:
		for doctype in ("Consent Record", "Lead Assignment", "Lead Activity", "Lead Task", "Site Visit"):
			frappe.db.delete(doctype, {"lead": ["in", leads]})
		frappe.db.delete("Lead Stage Change", {"parent": ["in", leads]})
	for doctype, names in (("Lead", leads), ("Client", clients)):
		if names:
			frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ["in", names]})
			frappe.db.delete("Comment", {"reference_doctype": doctype, "reference_name": ["in", names]})
			frappe.db.delete(doctype, {"name": ["in", names]})
	frappe.db.commit()  # nosemgrep
	return {"registrations": len(registrations), "leads": len(leads), "clients": len(clients)}


# --- Inventory (SOS-P4-01) ------------------------------------------------------------------------

GATE_INVENTORY_PREFIX = "Gate Inventory "


def _seed_inventory(admin, agent):
	"""The regression developer, project, units and property, through the inventory API. Safe to run again."""
	from sellos.inventory import api

	_seed_towers(admin)
	_seed_unit_grid(admin, agent)
	_seed_pricing(admin, agent)
	_seed_listings(admin, agent)
	if frappe.db.exists("Project", {"project_name": "Regression Heights"}):
		return
	with _as_user(admin):
		if not frappe.db.exists("Developer", "Regression Developer"):
			api.save_developer(
				{"developer_name": "Regression Developer", "contact_person": "Regression Sales"}
			)
		project = api.save_project(
			{
				"project_name": "Regression Heights",
				"developer": "Regression Developer",
				"rera_number": "P51800099001",
				"city": "Mumbai",
				"locality": "Andheri West",
				"project_status": "Under construction",
			}
		)["name"]
		units = {}
		for number, configuration, floor, area in (
			("1201", "2 BHK", 12, 640),
			("1202", "2 BHK", 12, 655),
			("1301", "3 BHK", 13, 910),
			("1302", "3 BHK", 13, 925),
		):
			units[number] = api.save_unit(
				{
					"project": project,
					"unit_number": number,
					"configuration": configuration,
					"floor": floor,
					"carpet_area": area,
					"parking": 1 if configuration == "2 BHK" else 2,
				}
			)["name"]
	with _as_user(agent):
		api.set_inventory_status("Unit", units["1301"], "Held", "Regression: buyer asked for two days")
		api.set_inventory_status("Unit", units["1302"], "Held")
		api.set_inventory_status("Unit", units["1302"], "Sold", "Regression: booking amount received")
		api.save_property(
			{
				"title": "Regression Resale Flat",
				"property_type": "Apartment",
				"city": "Pune",
				"locality": "Kothrud",
				"configuration": "2 BHK",
				"carpet_area": 720,
				"floor": 4,
				"parking": 1,
			}
		)


def _seed_towers(admin):
	"""Regression Towers, a project with Tower A (floors 1 to 3, the units 101 to 103 on floor 1), a possession
	date and two amenities, through the structure API (SOS-P7-05). Safe to run again."""
	from sellos.inventory import api, structure

	if frappe.db.exists("Project", {"project_name": "Regression Towers"}):
		return
	with _as_user(admin):
		if not frappe.db.exists("Developer", "Regression Developer"):
			api.save_developer(
				{"developer_name": "Regression Developer", "contact_person": "Regression Sales"}
			)
		project = api.save_project(
			{
				"project_name": "Regression Towers",
				"developer": "Regression Developer",
				"rera_number": "P51800099002",
				"city": "Mumbai",
				"locality": "Powai",
			}
		)["name"]
		for amenity in ("Swimming pool", "Gym"):
			structure.save_amenity(amenity)
		structure.save_project_details(project, "2028-03-31", ["Swimming pool", "Gym"])
		tower = structure.add_tower(project, "Tower A", "1 to 3")["name"]
		structure.generate_floor_units(tower, 1, "101 to 103", 520, "1 BHK")


def _seed_unit_grid(admin, agent):
	"""Regression Grid, a project with Tower G (floors 1 and 2) for the availability grid (SOS-P7-06), through
	the inventory, structure and hold APIs: G101 (2 BHK) and G103 (2 BHK) Available, G102 (3 BHK) held by the
	gate agent for Regression Buyer One, G104 (2 BHK) blocked by the Company Admin with the reason
	"Regression: legal hold", and G201 (1 BHK) Available. Safe to run again."""
	from sellos.inventory import api, holds, structure

	if frappe.db.exists("Project", {"project_name": "Regression Grid"}):
		return
	with _as_user(admin):
		project = api.save_project(
			{
				"project_name": "Regression Grid",
				"developer": "Regression Developer",
				"rera_number": "P51800099003",
				"city": "Mumbai",
				"locality": "Andheri",
			}
		)["name"]
		tower = structure.add_tower(project, "Tower G", "1 to 2")["name"]
		structure.generate_floor_units(tower, 1, "101 to 104", 640, "2 BHK", "G")
		structure.generate_floor_units(tower, 2, "201 to 201", 480, "1 BHK", "G")
		units = {u["unit_number"]: u["name"] for u in api.get_project(project)["units"]}
		api.save_unit({"configuration": "3 BHK"}, name=units["G102"])
		holds.block_unit(units["G104"], "Regression: legal hold")
	lead = frappe.db.get_value("Lead", {"lead_title": ["like", f"{REGRESSION_PREFIX}Buyer One%"]}, "name")
	if lead:
		with _as_user(agent):
			holds.hold_unit(units["G102"], lead)


def _seed_pricing(admin, agent):
	"""Regression Pricing, a project with one unit, the company percentages, a price list in force, two payment
	plans and one cost sheet, through the pricing and cost sheet APIs (SOS-P7-07). Safe to run again."""
	from sellos.inventory import api, cost_sheet, pricing

	if frappe.db.exists("Project", {"project_name": "Regression Pricing"}):
		return
	with _as_user(admin):
		if not frappe.db.exists("Developer", "Regression Developer"):
			api.save_developer(
				{"developer_name": "Regression Developer", "contact_person": "Regression Sales"}
			)
		project = api.save_project(
			{
				"project_name": "Regression Pricing",
				"developer": "Regression Developer",
				"rera_number": "P51800099004",
				"city": "Mumbai",
				"locality": "Powai",
			}
		)["name"]
		unit = api.save_unit(
			{
				"project": project,
				"unit_number": "1501",
				"configuration": "2 BHK",
				"floor": 12,
				"carpet_area": 650,
				"parking": 1,
			}
		)["name"]
		pricing.save_cost_settings(6, 1, 5)
		pricing.save_price_list(project, _gate_price_list("Regression Price List"))
		plan = pricing.save_payment_plan(
			project,
			{
				"plan_name": "Regression Construction Plan",
				"plan_type": "Construction linked",
				"instalments": [
					{"label": "On booking", "due_on": "On booking", "percent": 20},
					{"label": "On slab", "due_on": "On the 5th floor slab", "percent": 30},
					{"label": "On possession", "due_on": "On possession", "percent": 50},
				],
			},
		)["name"]
		pricing.save_payment_plan(
			project,
			{
				"plan_name": "Regression Time Plan",
				"plan_type": "Time linked",
				"instalments": [
					{"label": "Now", "days_after_booking": 0, "percent": 10},
					{"label": "After 30 days", "days_after_booking": 30, "percent": 90},
				],
			},
		)
	with _as_user(agent):
		cost_sheet.make_cost_sheet(unit, plan, ["Garden"])


def _seed_listings(admin, agent):
	"""Regression Listings: a published Primary listing of unit 1501 of Regression Pricing (Rs 1,05,00,000), a
	published Direct listing of the property Regression Resale Flat, and a Partner draft with no price, through
	the listing API as the gate agent (SOS-P4-02). Safe to run again."""
	from sellos.inventory import api, listings

	if frappe.db.exists("Listing", {"title": "Regression Primary 2 BHK"}):
		return
	pricing_project = frappe.db.get_value("Project", {"project_name": "Regression Pricing"}, "name")
	unit = frappe.db.get_value("Unit", {"project": pricing_project, "unit_number": "1501"}, "name")
	with _as_user(agent):
		prop = frappe.db.get_value("Property", {"title": "Regression Resale Flat"}, "name")
		if not prop:
			prop = api.save_property(
				{
					"title": "Regression Resale Flat",
					"property_type": "Apartment",
					"city": "Pune",
					"locality": "Baner",
					"carpet_area": 700,
				}
			)["name"]
		primary = listings.save_listing(
			{
				"title": "Regression Primary 2 BHK",
				"listing_type": "Primary",
				"unit": unit,
				"asking_price": 10500000,
				"description": "A two bedroom flat on the 12th floor with one parking slot.",
			}
		)["name"]
		listings.publish_listing(primary)
		direct = listings.save_listing(
			{
				"title": "Regression Direct Resale",
				"listing_type": "Direct",
				"property": prop,
				"asking_price": 8200000,
				"description": "A resale flat near the market, ready to move in.",
			}
		)["name"]
		listings.publish_listing(direct)
		listings.save_listing({"title": "Regression Partner Draft", "listing_type": "Partner"})


def _gate_price_list(title, on="2026-01-01"):
	"""The price list the pricing seed and spec share: Rs 12,000 per sq ft, floor rise Rs 100 above floor 4."""
	return {
		"title": title,
		"effective_from": on,
		"base_rate": 12000,
		"floor_rise_rate": 100,
		"floor_rise_from_floor": 4,
		"charges": [
			{
				"charge_type": "Preferred location",
				"charge_name": "Garden",
				"basis": "Rate per sq ft",
				"value": 150,
			},
			{"charge_type": "Parking", "charge_name": "Parking", "basis": "Amount", "value": 400000},
			{
				"charge_type": "Other",
				"charge_name": "Development",
				"basis": "Amount",
				"value": 250000,
				"always_apply": 1,
			},
		],
	}


def make_gate_pricing(prepared=1):
	"""A project with one unit (1201, 2 BHK, 650 sq ft, floor 12, 1 parking slot) for the cost sheet spec (tests
	only, SOS-P7-07). With `prepared`, the company percentages (6, 1 and 5), a price list in force, and the plans
	Gate Inventory Construction Plan (20, 30, 50) are made through the pricing API; without it, the project has
	none and the percentages are unset, so the spec makes them in the web app. remove_gate_pricing takes it all away."""
	from sellos.inventory import api, pricing

	_test_users()
	tag = frappe.generate_hash(length=6)
	with _as_user(TEST_USERS["company_admin"]["email"]):
		developer = api.save_developer({"developer_name": f"{GATE_INVENTORY_PREFIX}Pricing Developer {tag}"})
		project = api.save_project(
			{
				"project_name": f"{GATE_INVENTORY_PREFIX}Pricing {tag}",
				"developer": developer["name"],
				"rera_number": f"P5180{int(tag, 16) % 10**7:07d}",
				"city": "Mumbai",
			}
		)
		unit = api.save_unit(
			{
				"project": project["name"],
				"unit_number": "1201",
				"configuration": "2 BHK",
				"floor": 12,
				"carpet_area": 650,
				"parking": 1,
			}
		)["name"]
		if int(prepared):
			pricing.save_cost_settings(6, 1, 5)
			pricing.save_price_list(project["name"], _gate_price_list(f"{GATE_INVENTORY_PREFIX}List {tag}"))
			pricing.save_payment_plan(
				project["name"],
				{
					"plan_name": f"{GATE_INVENTORY_PREFIX}Construction Plan {tag}",
					"plan_type": "Construction linked",
					"instalments": [
						{"label": "On booking", "due_on": "On booking", "percent": 20},
						{"label": "On slab", "due_on": "On the 5th floor slab", "percent": 30},
						{"label": "On possession", "due_on": "On possession", "percent": 50},
					],
				},
			)
		else:
			frappe.db.set_single_value("SellOS Settings", "cost_rates_saved", 0)
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"project": project["name"], "unit": unit, "tag": tag}


def gate_pricing_state(project):
	"""A project's price lists, plans, the company percentages and its cost sheets, read back for the spec (tests
	only, SOS-P7-07)."""
	return {
		"price_lists": frappe.get_all("Price List", filters={"project": project}, pluck="title"),
		"plans": {
			row.plan_name: [i.percent for i in frappe.get_doc("Payment Plan", row.name).instalments]
			for row in frappe.get_all(
				"Payment Plan", filters={"project": project}, fields=["name", "plan_name"]
			)
		},
		"rates": [
			frappe.db.get_single_value("SellOS Settings", f)
			for f in ("stamp_duty_percent", "registration_percent", "gst_percent")
		],
		"sheets": [
			{"name": r.name, "total": r.total, "owner": r.owner, "stamp_duty_percent": r.stamp_duty_percent}
			for r in frappe.get_all(
				"Cost Sheet",
				filters={"project": project},
				fields=["name", "total", "owner", "stamp_duty_percent"],
				order_by="creation asc",
			)
		],
	}


def remove_gate_pricing():
	"""Remove the price lists, plans and cost sheets of the projects the pricing spec made, put the company
	percentages back to unset, and remove the projects (tests only, SOS-P7-07). The app never deletes them: this is
	the spec cleaning up after itself."""
	like = ["like", f"{GATE_INVENTORY_PREFIX}%"]
	for project in frappe.get_all("Project", filters={"project_name": like}, pluck="name"):
		for doctype, children in (
			("Cost Sheet", ("Cost Sheet Charge", "Cost Sheet Instalment")),
			("Price List", ("Price List Charge",)),
			("Payment Plan", ("Payment Plan Instalment",)),
		):
			for name in frappe.get_all(doctype, filters={"project": project}, pluck="name"):
				for child in children:
					frappe.db.delete(child, {"parent": name})
				frappe.db.delete("Version", {"ref_doctype": doctype, "docname": name})
				frappe.db.delete(doctype, {"name": name})
	frappe.db.set_single_value("SellOS Settings", "cost_rates_saved", 0)
	for field in ("stamp_duty_percent", "registration_percent", "gst_percent"):
		frappe.db.set_single_value("SellOS Settings", field, 0)
	return remove_gate_inventory()


def make_gate_grid():
	"""A project of Tower G with floors 1 and 2 and the Available units G101 and G102 (2 BHK) and G201 (1 BHK),
	and one lead the test agent owns, for the unit grid spec (tests only, SOS-P7-06). Made through the
	inventory and structure APIs as the Company Admin. Names start with "Gate Inventory " so
	remove_gate_inventory takes them away; the lead comes from seed_agent_leads, so remove_seeded_leads does."""
	from sellos.inventory import api, structure

	_test_users()
	tag = frappe.generate_hash(length=6)
	leads = seed_agent_leads()
	with _as_user(TEST_USERS["company_admin"]["email"]):
		developer = api.save_developer({"developer_name": f"{GATE_INVENTORY_PREFIX}Grid Developer {tag}"})
		project = api.save_project(
			{
				"project_name": f"{GATE_INVENTORY_PREFIX}Grid {tag}",
				"developer": developer["name"],
				"rera_number": f"P5180{int(tag, 16) % 10**7:07d}",
				"city": "Mumbai",
			}
		)["name"]
		tower = structure.add_tower(project, "Tower G", "1 to 2")["name"]
		structure.generate_floor_units(tower, 1, "101 to 102", 640, "2 BHK", "G")
		structure.generate_floor_units(tower, 2, "201 to 201", 480, "1 BHK", "G")
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	title = frappe.db.get_value("Lead", {"lead_title": ["like", f"%{leads['own']}%"]}, "lead_title")
	return {"project": project, "lead": title or leads["own"]}


def gate_unit_state(project, unit_number):
	"""A unit's status, holder and the number of rows in its status log, for the spec (tests only, SOS-P7-06)."""
	row = frappe.db.get_value(
		"Unit",
		{"project": project, "unit_number": unit_number},
		["name", "status", "held_by", "held_until"],
		as_dict=True,
	)
	log = frappe.get_all(
		"Inventory Status Change",
		filters={"parent": row.name},
		fields=["to_status", "changed_by", "reason"],
		order_by="idx asc",
	)
	return {
		"status": row.status,
		"held_by": row.held_by or "",
		"has_end": bool(row.held_until),
		"log": [[r.to_status, r.changed_by, r.reason or ""] for r in log],
	}


def gate_tower_state(project_name):
	"""Read back a project's towers, floors, units, possession date and amenities, for the spec (tests only,
	SOS-P7-05)."""
	project = frappe.get_doc("Project", {"project_name": project_name})
	towers = {}
	for tower in frappe.get_all("Project Tower", filters={"project": project.name}, pluck="name"):
		doc = frappe.get_doc("Project Tower", tower)
		towers[doc.tower_name] = {
			"archived": doc.archived,
			"floors": [row.floor_number for row in doc.floors],
			"units": sorted(
				frappe.get_all("Unit", filters={"tower": tower, "archived": 0}, pluck="unit_number")
			),
		}
	return {
		"towers": towers,
		"possession_date": str(project.possession_date or ""),
		"amenities": [row.amenity for row in project.amenities],
	}


def remove_gate_inventory():
	"""Remove the records the inventory spec made (names start with "Gate Inventory ") and what hangs on
	them (tests only, SOS-P4-01). The app never deletes inventory: this is the spec cleaning up after itself."""
	like = ["like", f"{GATE_INVENTORY_PREFIX}%"]
	projects = frappe.get_all("Project", filters={"project_name": like}, pluck="name")
	gate_units = frappe.get_all("Unit", filters={"project": ["in", projects or [""]]}, pluck="name")
	gate_properties = frappe.get_all("Property", filters={"title": like}, pluck="name")
	for listing in frappe.get_all(  # SOS-P4-02
		"Listing",
		or_filters={
			"title": like,
			"unit": ["in", gate_units or [""]],
			"property": ["in", gate_properties or [""]],
		},
		pluck="name",
	):
		frappe.db.delete("Listing Change", {"parent": listing})
		frappe.db.delete("Version", {"ref_doctype": "Listing", "docname": listing})
		frappe.db.delete("Listing", {"name": listing})
	for tower in frappe.get_all("Project Tower", filters={"project": ["in", projects or [""]]}, pluck="name"):
		frappe.db.delete("Version", {"ref_doctype": "Project Tower", "docname": tower})
	for unit in frappe.get_all("Unit", filters={"project": ["in", projects or [""]]}, pluck="name"):
		frappe.db.delete("Inventory Status Change", {"parent": unit})
		frappe.db.delete("Version", {"ref_doctype": "Unit", "docname": unit})
		frappe.db.delete("Unit", {"name": unit})
	for prop in frappe.get_all("Property", filters={"title": like}, pluck="name"):
		frappe.db.delete("Inventory Status Change", {"parent": prop})
		frappe.db.delete("Version", {"ref_doctype": "Property", "docname": prop})
		frappe.db.delete("Property", {"name": prop})
	for name in projects:
		frappe.db.delete("Version", {"ref_doctype": "Project", "docname": name})
		frappe.db.delete("Project Tower", {"project": name})
		frappe.db.delete("Project", {"name": name})
	for name in frappe.get_all("Amenity", filters={"amenity_name": like}, pluck="name"):
		frappe.db.delete("Version", {"ref_doctype": "Amenity", "docname": name})
		frappe.db.delete("Amenity", {"name": name})
	for name in frappe.get_all("Developer", filters={"developer_name": like}, pluck="name"):
		frappe.db.delete("Version", {"ref_doctype": "Developer", "docname": name})
		frappe.db.delete("Developer", {"name": name})
	frappe.db.commit()  # nosemgrep
	return {"projects": len(projects)}


def make_gate_listings():
	"""A project with the Available unit 1201 and a secondary property, for the listing spec (tests only,
	SOS-P4-02). Names start with "Gate Inventory " so remove_gate_inventory takes them away, listings too."""
	from sellos.inventory import api

	_test_users()
	tag = frappe.generate_hash(length=6)
	with _as_user(TEST_USERS["company_admin"]["email"]):
		developer = api.save_developer({"developer_name": f"{GATE_INVENTORY_PREFIX}Listing Developer {tag}"})
		project = api.save_project(
			{
				"project_name": f"{GATE_INVENTORY_PREFIX}Listing {tag}",
				"developer": developer["name"],
				"rera_number": f"P5180{int(tag, 16) % 10**7:07d}",
				"city": "Mumbai",
			}
		)
		api.save_unit(
			{
				"project": project["name"],
				"unit_number": "1201",
				"configuration": "2 BHK",
				"floor": 12,
				"carpet_area": 650,
			}
		)
		api.save_property(
			{
				"title": f"{GATE_INVENTORY_PREFIX}Listing Flat {tag}",
				"property_type": "Apartment",
				"city": "Pune",
				"carpet_area": 700,
			}
		)
	frappe.db.commit()  # the browser reads it from another process  # nosemgrep
	return {"project_name": f"{GATE_INVENTORY_PREFIX}Listing {tag}", "tag": tag}


def gate_listing_state(title):
	"""Read back a listing by title, for the spec (tests only, SOS-P4-02)."""
	doc = frappe.get_doc("Listing", {"title": title})
	return {
		"listing_type": doc.listing_type,
		"published": doc.published,
		"asking_price": doc.asking_price,
		"target": doc.unit or doc.property,
		"changes": [[c.field_label, c.old_value, c.new_value, c.changed_by] for c in doc.changes],
	}


def gate_project_state(project_name):
	"""Read back a project, its RERA number and its units with each status log, for the spec (tests only,
	SOS-P4-01)."""
	project = frappe.get_doc("Project", {"project_name": project_name})
	units = frappe.get_all(
		"Unit", filters={"project": project.name}, fields=["name", "unit_number", "status", "carpet_area"]
	)
	return {
		"rera_number": project.rera_number,
		"units": {
			u.unit_number: {
				"status": u.status,
				"carpet_area": u.carpet_area,
				"log": [r.to_status for r in frappe.get_doc("Unit", u.name).status_log],
			}
			for u in units
		},
	}


# --- The inbound opt in route (SOS-P2-08) ---------------------------------------------------------

ENQUIRY_SEED = 3901
ENQUIRY_WORDING = "Gate wording: I agree to be called back by the company about properties."
INBOUND_SEEDS = {"one": 1401, "stop": 1402, "missed": 1403}


def _seed_inbound_opt_in():
	"""Two enquiry page leads and one missed call lead, through the production intake function. Safe to
	run again: a number that already belongs to a client is left alone."""
	from sellos.crm import intake
	from sellos.crm.duplicates import normalise_phone
	from sellos.telephony import inbound
	from sellos.telephony.base import CallEvent

	def new(key):
		return not frappe.db.exists(
			"Client", {"phone_key": normalise_phone(phones.in_mobile(INBOUND_SEEDS[key]))}
		)

	for key, name, stop in (
		("one", f"{REGRESSION_PREFIX}Enquiry One", None),
		("stop", f"{REGRESSION_PREFIX}Enquiry Stop", "Website"),
	):
		if new(key):
			intake.take(
				phone=phones.in_mobile(INBOUND_SEEDS[key]),
				source="Website",
				campaign="Enquiry page",
				kind="enquiry",
				reference=f"regression-{key}",
				evidence={"page": "enquiry", "wording": ENQUIRY_WORDING, "regression": True},
				name=name,
				notes="Sent the enquiry page.",
				stop_source=stop,
			)
	our_number = inbound.our_number()
	if our_number and new("missed"):
		inbound.handle_missed_call(
			CallEvent(
				call_id="regression-missed-call",
				state="no-answer",
				from_number=phones.in_mobile(INBOUND_SEEDS["missed"]),
				to_number=our_number,
				direction="inbound",
			)
		)


def seed_enquiry_page():
	"""What the enquiry page spec needs (SOS-P2-08): the company's consent wording, the form key of the
	link, and the phone number the spec types, from sellos.tests.phones. Returns {"key", "phone",
	"wording"}. remove_enquiry_page puts it all back."""
	from sellos.access.public_intake import form_key

	remove_enquiry_page()
	frappe.db.set_single_value("SellOS Settings", "consent_wording", ENQUIRY_WORDING)
	key = form_key()
	frappe.db.commit()  # the browser is another process  # nosemgrep
	return {"key": key, "phone": phones.in_mobile(ENQUIRY_SEED), "wording": ENQUIRY_WORDING}


def enquiry_outcome(phone=None):
	"""The lead state a spec checks after the enquiry page is submitted: whether there is a lead for the
	number, its source, stage, consent status, records and whether the evidence is a private file."""
	from sellos.crm.duplicates import normalise_phone

	client = frappe.db.get_value(
		"Client", {"phone_key": normalise_phone(phone or phones.in_mobile(ENQUIRY_SEED))}, "name"
	)
	lead = (
		frappe.db.get_value(
			"Lead", {"client": client}, ["name", "source", "stage", "consent_status"], as_dict=True
		)
		if client
		else None
	)
	if not lead:
		return {"lead": None}
	records = frappe.get_all("Consent Record", {"lead": lead.name}, ["basis", "evidence_link", "expires_on"])
	return {
		"lead": lead.name,
		"source": lead.source,
		"stage": lead.stage,
		"consent_status": lead.consent_status,
		"records": [r.basis for r in records],
		"evidence_private": all((r.evidence_link or "").startswith("/private/files/") for r in records),
		"activities": frappe.db.count("Lead Activity", {"lead": lead.name}),
		"first_stage": pipeline.first_stage(),
	}


def remove_enquiry_page():
	"""Remove what the enquiry page spec made (tests only): its lead, files and the wording it set."""
	from sellos.crm.duplicates import normalise_phone

	client = frappe.db.get_value(
		"Client", {"phone_key": normalise_phone(phones.in_mobile(ENQUIRY_SEED))}, "name"
	)
	if client:
		leads = frappe.get_all("Lead", filters={"client": client}, pluck="name")
		if leads:
			frappe.db.delete("File", {"attached_to_doctype": "Lead", "attached_to_name": ["in", leads]})
		frappe.db.set_value("Client", client, "client_name", f"Gate Enquiry {client}")
	remove_seeded_leads()
	frappe.db.set_single_value("SellOS Settings", "consent_wording", "")
	frappe.cache.delete_keys("sellos_intake_rate")
	frappe.cache.delete_keys("sellos_webhook_rate")
	frappe.db.commit()  # nosemgrep
	return {"removed": True}
