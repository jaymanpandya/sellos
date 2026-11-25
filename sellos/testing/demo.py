"""The SellOS demo environment (SOS-DEMO-1): a control site and two company sites to look at in a browser.

    python -m sellos.testing.demo seed|migrate|reset|status|sites      (scripts/demo.sh runs it)

No gate touches these sites. They are named sellos_tenant_demo<anything>.localhost, which the gate's
site check, clean check and leak check ignore, and which tenant_sites.drop refuses unless this module
sets SELLOS_DEMO_ALLOW_DROP for its own drops.

The sites are built the way a real tenant is: the control site holds a Tenant and a Provisioning Job,
and the provisioning worker (sellos.provisioning.worker) makes the site with the MariaDB provisioner
account, installs SellOS and configures the Company Admin. Then the data and the users are added.

SAFETY: every function that writes users, passwords or data first calls check_demo_site(), which refuses
any site that is not sellos_tenant_demo<letters and digits>.localhost. The sign in passwords are known
and simple (DEMO_PASSWORD), so they must never exist anywhere else.
"""

import contextlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEMO_SITE = re.compile(r"^sellos_tenant_demo[a-z0-9]*\.localhost$")
DEMO_ID = re.compile(r"^demo[a-z0-9]*$")
ALLOW_DROP_ENV = "SELLOS_DEMO_ALLOW_DROP"

CONTROL_ID = "democontrol"
COMPANY_IDS = ("demobom", "demoamd")
PORT = 8006
DEMO_PASSWORD = "Demo@2026"
EMAIL_DOMAIN = "demo.example.com"
PLATFORM_ADMIN_EMAIL = f"platform@{EMAIL_DOMAIN}"

PLATFORM_ADMIN = "SellOS Platform Admin"
COMPANY_ADMIN = "SellOS Company Admin"
AGENT = "SellOS Agent"
CHANNEL_PARTNER = "SellOS Channel Partner"
CLIENT = "SellOS Client"
SALES_MANAGER = "SellOS Sales Manager"


class DemoRefused(RuntimeError):
	"""The demo code was pointed at a site that is not a demo site."""


class DemoSeedFailed(RuntimeError):
	"""One or more seed steps failed on a site. Names every step and its error."""


# The steps of this process's seed that failed, as {"step", "error"}. seed_company returns them, and seed()
# raises DemoSeedFailed for them after every site has been tried, so a failure is never just a missing section.
STEP_FAILURES = []


COMPANIES = (
	{"name": "Pandya Realtors - BOM", "city": "Mumbai", "word": "bom"},
	{"name": "Pandya Realtors - AMD", "city": "Ahmedabad", "word": "amd"},
)

DEMO_TELEPHONY_PLAN = ()  # the calls themselves are made by demo_crm


def company_users(index):
	"""(email, name, role) of the company's sign ins, in the order docs/DEMO.md lists them: the Company Admin, the
	Sales Manager, four agents, the Channel Partner and the Client."""
	from sellos.testing import demo_names

	data = COMPANIES[index % len(COMPANIES)]
	word = data["word"]
	staff = demo_names.STAFF[word]
	rows = [
		(_addr("admin", word), staff["admin"], COMPANY_ADMIN),
		(sales_manager_email(word), staff["manager"], SALES_MANAGER),
	]
	for number, name in enumerate(staff["agents"], 1):
		rows.append((_addr(f"agent{number}", word), name, AGENT))
	rows.append((_addr("partner", word), staff["partner"], CHANNEL_PARTNER))
	rows.append((_addr("client", word), staff["client"], CLIENT))
	return rows


def users_of(index):
	"""The same people as a dict of emails for the builders' context."""
	rows = company_users(index)
	return {
		"admin": rows[0][0],
		"manager": rows[1][0],
		"agents": [email for email, _n, role in rows if role == AGENT],
		"partner": next(email for email, _n, role in rows if role == CHANNEL_PARTNER),
		"client": next(email for email, _n, role in rows if role == CLIENT),
	}


def seed_company(index=0):
	"""On a company site: roles, stages, sources, the people who sign in, then every builder in order (inventory,
	crm, inventory holds, sales, whatsapp), then the checks. Each builder looks a record up before it creates it, so
	repeating this creates nothing. Prints a summary of what was created, renamed and removed per doctype."""
	import frappe

	from sellos.access.roles import ensure_roles
	from sellos.crm import call_outcomes, lead_sources, pipeline
	from sellos.testing import demo_ctx, demo_names

	site = check_demo_site()
	del STEP_FAILURES[:]
	data = COMPANIES[int(index) % len(COMPANIES)]
	ensure_roles()
	pipeline.ensure_default_stages()
	lead_sources.ensure_default_sources()
	call_outcomes.ensure_defaults()  # a lead moved to Closed lost records a reason

	settings = frappe.get_single("SellOS Settings")
	settings.company_name = data["name"]
	settings.city = data["city"]
	settings.contact_email = f"hello@{data['word']}.{EMAIL_DOMAIN}"
	settings.setup_complete = 1
	settings.save(ignore_permissions=True)

	_ensure_user(PLATFORM_ADMIN_EMAIL, "Demo Platform Admin", [PLATFORM_ADMIN])
	for email, name, role in company_users(index):
		_ensure_user(email, name, [role])
	users = users_of(index)
	staff = demo_names.STAFF[data["word"]]
	ctx = demo_ctx.Ctx(
		word=data["word"],
		company_name=data["name"],
		users=users,
		staff_names={**staff},
	)
	_support_grants(users["admin"])
	_seed_features(index, data, users, ctx)
	_isolated("remove regression records", remove_regression_records)
	frappe.db.commit()  # nosemgrep  bench execute commits too
	_print_summary(site, ctx)
	return {
		"site": site,
		"leads": frappe.db.count("Lead"),
		"summary": dict(ctx.summary),
		"failed_steps": list(STEP_FAILURES),
	}


def _seed_features(index, data, users, ctx):
	"""Settings the company needs, then the builders. A failed builder is rolled back, printed and recorded, and the
	next one still runs (seed fails loudly at the end)."""
	import frappe

	from sellos.testing import demo_crm, demo_inventory, demo_sales, demo_whatsapp

	admin, agents = users["admin"], users["agents"]
	frappe.db.set_single_value(
		"SellOS Settings", "consent_wording", DEMO_CONSENT_WORDING.format(company=data["name"])
	)
	_seed_telephony_demo(index, admin)
	_seed_sales_team(data, admin, agents, users["manager"])
	_seed_do_not_call(admin)
	frappe.db.commit()  # nosemgrep  so a failed step below rolls back only itself
	for label, function in (
		("inventory", demo_inventory.build),
		("crm", demo_crm.build),
		("inventory holds and sales", demo_inventory.hold_and_sell),
		("sales", demo_sales.build),
		("whatsapp", demo_whatsapp.build),
	):
		_isolated(label, function, ctx)
	_isolated("minimums", _check_minimums, ctx)


def _check_minimums(ctx):
	"""The demo brief's minimum volumes, read back from the site. Raises with every shortfall."""
	import frappe

	from sellos.testing import demo_ctx

	m = demo_ctx.MINIMUMS
	have = {
		"developers": frappe.db.count("Developer"),
		"projects": frappe.db.count("Project"),
		"properties": frappe.db.count("Property"),
		"leads": frappe.db.count("Lead", {"pipeline": "Buyer"})
		if frappe.get_meta("Lead").has_field("pipeline")
		else frappe.db.count("Lead"),
		"site_visits": frappe.db.count("Site Visit"),
		"deals": frappe.db.count("Deal"),
		"payouts": frappe.db.count("Commission Payout"),
		"partners": frappe.db.count("Channel Partner Firm"),
		"whatsapp_conversations": frappe.db.count("WhatsApp Conversation"),
		"mandates": frappe.db.count("Mandate"),
		"call_logs": frappe.db.count("Call Log"),
	}
	short = [f"{key}: {have[key]} of {m[key]}" for key in have if key in m and have[key] < m[key]]
	if short:
		raise RuntimeError("below the demo minimums: " + "; ".join(short))


def _print_summary(site, ctx):
	"""What the seed created, renamed and removed on this site, per doctype."""
	print(f"DEMO SUMMARY {site}:")
	for key in sorted(ctx.summary):
		print(f"  {key}: {ctx.summary[key]}")


# --- The one safety check ------------------------------------------------------------------------


def is_demo_site(site) -> bool:
	return isinstance(site, str) and bool(DEMO_SITE.fullmatch(site))


def check_demo_site(site=None):
	"""Refuse anything that is not a localhost site named sellos_tenant_demo<id>.localhost."""
	if site is None:
		import frappe

		site = getattr(frappe.local, "site", None)
	if not is_demo_site(site):
		raise DemoRefused(
			f"Refusing to run on {site!r}. The demo seed runs only on sites named "
			"sellos_tenant_demo<id>.localhost, because it writes users with known passwords."
		)
	return site


def check_demo_id(tenant_id):
	if not isinstance(tenant_id, str) or not DEMO_ID.fullmatch(tenant_id):
		raise DemoRefused(
			f"Refusing demo id {tenant_id!r}: a demo id is demo followed by letters and digits."
		)
	return tenant_id


def site_of(tenant_id):
	from sellos.provisioning import tenant_sites

	return tenant_sites.names(check_demo_id(tenant_id))[0]


# --- Steps that run ON a demo site (bench execute) -----------------------------------------------


def _ensure_user(email, first_name, roles, password=DEMO_PASSWORD):
	import frappe
	from frappe.utils.password import update_password

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": first_name, "send_welcome_email": 0}
		)
	user.enabled = 1
	user.flags.ignore_permissions = True
	have = {row.role for row in user.get("roles", [])}
	for role in roles:
		if role not in have:
			user.append("roles", {"role": role})
	# Saving a User queues a Contact job that would run after this process ends. Make the Contact inside
	# this save, as sellos.provisioning.tenant_setup does.
	previous = frappe.flags.in_install
	frappe.flags.in_install = "sellos"
	try:
		user.save()
	finally:
		frappe.flags.in_install = previous
	update_password(email, password)
	return email


def setup_control():
	"""On the control site: the control flag, no outgoing email, the link address, a plan, the Platform Admin."""
	import frappe
	from frappe.installer import update_site_config

	from sellos.access.roles import ensure_roles

	check_demo_site()
	ensure_roles()
	update_site_config("sellos_control_site", 1)
	update_site_config("mute_emails", 1)  # the worker's login email is queued for nobody
	update_site_config("sellos_tenant_url_template", "http://{site}:" + str(PORT))
	if not frappe.db.exists("Plan", "Demo"):
		frappe.get_doc(
			{
				"doctype": "Plan",
				"plan_name": "Demo",
				"enabled": 1,
				"max_users": 25,
				"description": "The demo plan.",
			}
		).insert(ignore_permissions=True)
	_ensure_user(PLATFORM_ADMIN_EMAIL, "Demo Platform Admin", [PLATFORM_ADMIN])
	frappe.db.commit()  # nosemgrep  bench execute commits too
	remove_regression_records()
	return {"site": frappe.local.site, "users": [PLATFORM_ADMIN_EMAIL]}


def _addr(role_word, company_word):
	return f"{role_word}.{company_word}@{EMAIL_DOMAIN}"


def _support_grants(admin):
	"""One active and one revoked grant to the Platform Admin. An expired active grant is renewed."""
	import frappe
	from frappe.utils import now_datetime

	from sellos.access import support

	support.expire_due_grants()
	rows = frappe.get_all("Support Grant", fields=["status", "starts_at", "expires_at"])
	states = {support.effective_status(r.status, r.starts_at, r.expires_at) for r in rows}

	def grant(minutes, reason):
		doc = frappe.get_doc(
			{
				"doctype": "Support Grant",
				"support_user": PLATFORM_ADMIN_EMAIL,
				"duration_minutes": minutes,
				"reason": reason,
			}
		)
		doc.insert(ignore_permissions=True)
		# The grant took the session user (Administrator) as its author. The Company Admin gave it.
		frappe.db.set_value("Support Grant", doc.name, "granted_by", admin, update_modified=False)
		support.write_log(doc.name, "Granted", user=admin)
		return doc

	if "Active" not in states:
		grant(240, "Demo: help with the pipeline setup")
	if "Revoked" not in states:
		second = grant(60, "Demo: a check that was finished early")
		second.reload()  # granted_by was set in the database above
		second.status = "Revoked"
		second.revoked_at = now_datetime()
		second.revoked_by = admin
		second.save(ignore_permissions=True)
		support.write_log(second.name, "Revoked", user=admin)


# --- The regression seed's "Regression ..." records, removed from the demo sites only ------------------------
# The first demo sites were seeded on top of the regression data (sellos/tests/ui_fixtures.seed_regression_data),
# so "Regression Partner Buyer" and the like showed beside the Mumbai content. remove_regression_records() takes
# them out, on a demo site only (check_demo_site refuses sellos_test and every other site), and prints what it
# removed. It is safe to repeat: the second run finds nothing. The CRM refuses a delete through the app, so, as the
# test fixtures do, this goes to the tables. A record that a non Regression record still links to is kept and
# reported, never deleted out from under it. The four regression_partner_* users are left: a user is linked from
# the owner and modified by fields of every record.

REGRESSION_LIKE = "Regression%"
# The doctypes whose rows belong to a project (a project link field), removed with it.
PROJECT_PARTS = (
	"Project Tower",
	"Price List",
	"Payment Plan",
	"Cost Sheet",
	"Commission Payout",
	"Commission Rate",
	"Partner Share",
)


def _present(doctype):
	import frappe

	return frappe.db.table_exists(doctype)


def _names(doctype, field, extra=None, like=REGRESSION_LIKE):
	import frappe

	if not _present(doctype):
		return []
	filters = {field: ["like", like]} if field else {}
	filters.update(extra or {})
	return frappe.get_all(doctype, filters=filters, pluck="name")


def _regression_families(like=REGRESSION_LIKE):
	"""[(label, {doctype: [names]})]: a Regression project with everything that belongs to it, and each Regression
	property, listing and developer on its own."""
	import frappe

	families = []
	for project in _names("Project", "project_name", like=like):
		family = {"Project": [project]}
		units = _names("Unit", None, {"project": project})
		family["Unit"] = units
		for doctype in PROJECT_PARTS:
			family[doctype] = _names(doctype, None, {"project": project})
		if units and _present("Cost Sheet"):
			family["Cost Sheet"] = sorted(
				set(family["Cost Sheet"])
				| set(frappe.get_all("Cost Sheet", {"unit": ["in", units]}, pluck="name"))
			)
		families.append((f"Project {project}", {k: v for k, v in family.items() if v}))
	for doctype, field in (("Property", "title"), ("Listing", "title"), ("Developer", "developer_name")):
		for name in _names(doctype, field, like=like):
			families.append((f"{doctype} {name}", {doctype: [name]}))
	return families


def _referrers(doctype, names, doomed):
	"""[(doctype, name)] of every row outside `doomed` that links to one of these names. A row of a child table
	counts as its parent."""
	import frappe

	found = []
	docfield = frappe.qb.DocType("DocField")
	fields = (
		frappe.qb.from_(docfield)
		.select(docfield.parent, docfield.fieldname)
		.where((docfield.fieldtype == "Link") & (docfield.options == doctype))
		.run(as_dict=True)
	)
	for field in fields:
		referrer = field.parent
		if not _present(referrer) or not frappe.db.exists("DocType", {"name": referrer, "module": "SellOS"}):
			continue
		table = frappe.qb.DocType(referrer)
		if frappe.get_meta(referrer).istable:
			rows = (
				frappe.qb.from_(table)
				.select(table.parenttype, table.parent)
				.where(table[field.fieldname].isin(names))
				.run()
			)
		else:
			rows = [
				(referrer, name)
				for (name,) in frappe.qb.from_(table)
				.select(table.name)
				.where(table[field.fieldname].isin(names))
				.run()
			]
		for rdoctype, rname in rows:
			if rname not in doomed.get(rdoctype, set()):
				found.append((rdoctype, rname))
	return found


def _delete_rows(doctype, names):
	import frappe

	for table_field in frappe.get_meta(doctype).get_table_fields():
		frappe.db.delete(table_field.options, {"parent": ["in", names], "parenttype": doctype})
	frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ["in", names]})
	frappe.db.delete(doctype, {"name": ["in", names]})


def _purge_regression(like=REGRESSION_LIKE):
	"""The removal itself, with no site check, for the records whose name matches `like`. remove_regression_records
	calls it with the Regression pattern, on a demo site only; the tests call it with a pattern of their own, so
	they can never touch the Regression records of sellos_test. Returns what it removed and what it kept."""
	import frappe

	from sellos.tests import ui_fixtures

	removed = {}
	if _present("Client"):
		clients = _names("Client", "client_name", like=like)
		counts = ui_fixtures.remove_clients(clients)
		removed.update({k: v for k, v in counts.items() if v})
	families = _regression_families(like)
	kept = []
	while True:
		doomed = {}
		for _, family in families:
			for doctype, names in family.items():
				doomed.setdefault(doctype, set()).update(names)
		blocked = []
		for label, family in families:
			reasons = []
			for doctype, names in family.items():
				reasons += _referrers(doctype, names, doomed)
			if reasons:
				blocked.append((label, sorted(set(reasons))[:3]))
		if not blocked:
			break
		labels = {label for label, _ in blocked}
		kept += [f"{label} (still linked from {reasons})" for label, reasons in blocked]
		families = [(label, family) for label, family in families if label not in labels]
	for _, family in families:
		for doctype in ("Cost Sheet", "Commission Payout", "Partner Share", "Listing", "Unit"):
			if family.get(doctype):
				_delete_rows(doctype, family[doctype])
				removed[doctype] = removed.get(doctype, 0) + len(family[doctype])
		for doctype, names in family.items():
			if doctype not in ("Cost Sheet", "Commission Payout", "Partner Share", "Listing", "Unit"):
				_delete_rows(doctype, names)
				removed[doctype] = removed.get(doctype, 0) + len(names)
	frappe.db.commit()  # nosemgrep  bench execute commits too
	return {"removed": removed, "kept": kept}


def remove_regression_records():
	"""Remove the "Regression ..." records from a demo site (democontrol, demobom, demoamd) and print what went.
	Refuses any other site. Safe to repeat."""
	site = check_demo_site()
	result = _purge_regression()
	print(f"DEMO: removed from {site}: {json.dumps(result['removed']) if result['removed'] else 'nothing'}")
	for line in result["kept"]:
		print(f"DEMO: kept on {site}: {line}")
	return {"site": site, **result}


# --- Every feature built so far (SOS-DEMO-2) ---------------------------------------------------------
# The demo's content is realistic and made at scale by one builder module per area (demo_inventory, demo_crm,
# demo_sales, demo_whatsapp), each reading demo_names and the context of demo_ctx and going through the production
# APIs. The regression seed's "Regression ..." records are not used here. Everything below is safe to run again.

SALES_PASSWORD_WORD = "sales"
DEMO_TELEPHONY_ID = "FAKEOK-DEMO-NOT-A-REAL-KEY"  # FAKEOK: the fake provider accepts it
DEMO_TELEPHONY_TOKEN = "fake-demo-token-not-a-real-key"
DEMO_CONSENT_WORDING = (
	"I agree that {company} may call, WhatsApp and email me about properties that match my needs. "
	"I can withdraw this at any time."
)


def sales_manager_email(word):
	return f"{SALES_PASSWORD_WORD}.{word}@{EMAIL_DOMAIN}"


def _as(email):
	"""Run as a user, then go back (the regression seed's own helper, so the demo holds no set_user)."""
	from sellos.tests import ui_fixtures

	return ui_fixtures._as_user(email)


def _seed_telephony_demo(index, admin):
	"""Fake Telephony Settings: obviously fake keys, a 022 number, and the fake provider, so no call leaves."""
	import frappe
	from frappe.installer import update_site_config

	from sellos.telephony import settings
	from sellos.tests import phones

	check_demo_site()
	# The fake provider runs only on a site that allows tests (sellos.telephony.provider.get_provider). A demo
	# site never holds a real key, so its calls are fake by design and none can leave the machine.
	update_site_config("allow_tests", 1)
	frappe.conf.allow_tests = 1
	frappe.db.set_single_value("Telephony Settings", "provider", "fake")
	with _as(admin):
		# Saved every time, so a site that took earlier values gets these. Same values twice change nothing.
		number = "022" + phones.in_mobile(3100 + int(index))[-8:]
		settings.save_telephony_settings(
			auth_id=DEMO_TELEPHONY_ID, auth_token=DEMO_TELEPHONY_TOKEN, phone_number=number
		)


def _seed_sales_team(data, admin, agents, manager=None):
	"""A Sales Manager and a team holding the four agents, so Teams and the Team report show data."""
	import frappe

	from sellos.access import teams

	manager = manager or sales_manager_email(data["word"])
	name = f"{data['name']} Sales Team"
	if frappe.db.exists("Sales Team", name):
		return
	with _as(admin):
		teams.save_team(values={"team_name": name, "manager": manager, "members": list(agents)})


def _seed_do_not_call(admin):
	"""A few numbers on the do not call list. They belong to nobody on the demo, so no lead changes."""
	import frappe

	from sellos.telephony import dnd
	from sellos.tests import phones

	if frappe.db.count("Do Not Call Number"):
		return
	numbers = "\n".join(phones.in_mobile(seed) for seed in (3201, 3202, 3203, 3204))
	with _as(admin):
		dnd.import_do_not_call_list(numbers, "Demo: the national list")


def _isolated(label, function, *args):
	"""Run one seed step. A failure is rolled back to the last commit, printed and recorded in STEP_FAILURES;
	the next step still runs, and seed() fails loudly at the end."""
	import traceback

	import frappe

	try:
		result = function(*args)
		frappe.db.commit()  # nosemgrep  bench execute commits too
		return result
	except Exception as e:
		frappe.db.rollback()
		STEP_FAILURES.append({"step": label, "error": f"{type(e).__name__}: {e}"})
		print(f"DEMO SEED STEP FAILED: {label}\n{traceback.format_exc()}", file=sys.stderr)
		return None


# --- The orchestration (plain Python, run with the bench's own interpreter) -----------------------


def _bench():
	from sellos.provisioning import tenant_sites

	return tenant_sites.bench_dir()


def _site_exists(site):
	return (_bench() / "sites" / site / "site_config.json").is_file()


def _run_on(site, function, **kwargs):
	"""Run one function of this module on a demo site with bench execute (which commits)."""
	from sellos.provisioning import site_script

	check_demo_site(site)
	return site_script._site_command(
		site, "execute", f"sellos.testing.demo.{function}", "--kwargs", repr(kwargs)
	)


@contextlib.contextmanager
def _control_connection(site):
	import frappe

	bench = _bench()
	previous = os.getcwd()
	os.chdir(bench / "sites")
	frappe.init(site=site, sites_path=str(bench / "sites"))
	frappe.connect()  # as Administrator, as the worker's own main does
	try:
		yield
	finally:
		frappe.destroy()
		os.chdir(previous)


def ensure_control(control_id=CONTROL_ID):
	"""The control site: made with the provisioner account, SellOS installed, then set up."""
	from sellos.provisioning import site_script, tenant_sites

	site = site_of(control_id)
	if not _site_exists(site):
		print(f"Creating the control site {site} ...")
		tenant_sites.create(control_id)
		site_script._site_command(site, "install-app", site_script.APP)
	_run_on(site, "setup_control")
	return site


def provision_companies(control_id, company_ids):
	"""Ask the control site's worker for each missing company site, exactly as a real tenant is made."""
	import frappe

	from sellos.provisioning import status, worker

	control = site_of(control_id)
	with _control_connection(control):
		for i, tenant_id in enumerate(company_ids):
			data = COMPANIES[i % len(COMPANIES)]
			site = site_of(tenant_id)
			tenant = frappe.db.get_value("Tenant", tenant_id, ["status"], as_dict=True)
			if tenant and tenant.status == status.ACTIVE and _site_exists(site):
				continue
			if not tenant:
				frappe.get_doc(
					{
						"doctype": "Tenant",
						"tenant_id": tenant_id,
						"company_name": data["name"],
						"plan": "Demo",
						"admin_name": f"{data['name']} Admin",
						"admin_email": company_users(i)[0][0],
					}
				).insert()
				# Tenant.after_insert makes its Provisioning Job.
				frappe.db.commit()  # nosemgrep  the worker reads these in its own transaction
		while worker.process_next():
			frappe.db.commit()  # nosemgrep
		for tenant_id in company_ids:
			state = frappe.db.get_value("Tenant", tenant_id, "status")
			if state != status.ACTIVE:
				log = frappe.db.get_value("Provisioning Job", {"tenant": tenant_id}, "log") or ""
				raise RuntimeError(
					f"{tenant_id} is {state}, not Active. Last log lines:\n"
					+ "\n".join(log.splitlines()[-8:])
				)


def seed(control_id=CONTROL_ID, company_ids=COMPANY_IDS):
	for tenant_id in (control_id, *company_ids):
		check_demo_id(tenant_id)
	ensure_control(control_id)
	provision_companies(control_id, company_ids)
	failures = []
	for i, tenant_id in enumerate(company_ids):
		site = site_of(tenant_id)
		print(f"Seeding {site} ...")
		last = (_run_on(site, "seed_company", index=i).strip().splitlines() or ["{}"])[-1]
		print(last)
		failures += failed_steps_of(site, last)
	if failures:
		raise DemoSeedFailed(
			f"{len(failures)} seed step(s) failed (the rest of the demo is seeded; the full traceback of each "
			"is in the output above, and repeating the seed retries only what is missing):\n"
			+ "\n".join(f"  {site}: step '{step}': {error}" for site, step, error in failures)
		)
	print(urls(control_id, company_ids))


def failed_steps_of(site, result_line):
	"""The (site, step, error) of every failed step in seed_company's result line. A line that is not the
	result at all is itself a failure, so a changed output format cannot hide one."""
	try:
		result = json.loads(result_line)
		return [(site, f["step"], f["error"]) for f in result["failed_steps"]]
	except (ValueError, KeyError, TypeError):
		return [(site, "(the seed's result)", f"not understood: {result_line[:200]!r}")]


def migrate_all(control_id=CONTROL_ID, company_ids=COMPANY_IDS):
	"""Migrate every demo site that exists, so new doctypes and fields are there before the seed. Never
	creates, drops or wipes anything, and migrating again changes nothing."""
	for tenant_id in (control_id, *company_ids):
		site = site_of(check_demo_id(tenant_id))
		if _site_exists(site):
			from sellos.provisioning import site_script

			check_demo_site(site)
			print(f"Migrating {site} ...")
			site_script._site_command(site, "migrate")


def drop_all(control_id=CONTROL_ID, company_ids=COMPANY_IDS):
	"""Drop the demo sites and their databases. The only code that may: it sets the allow flag itself."""
	from sellos.provisioning import tenant_sites

	os.environ[ALLOW_DROP_ENV] = "1"
	try:
		for tenant_id in (*company_ids, control_id):
			site = site_of(tenant_id)
			if _site_exists(site):
				print(f"Dropping {site} ...")
				tenant_sites.drop(tenant_id)
	finally:
		os.environ.pop(ALLOW_DROP_ENV, None)


def reset(control_id=CONTROL_ID, company_ids=COMPANY_IDS):
	drop_all(control_id, company_ids)
	seed(control_id, company_ids)


def serving(port=PORT, site=None):
	"""True when the demo server answers ping for the site's Host header."""
	request = urllib.request.Request(
		f"http://127.0.0.1:{port}/api/method/ping", headers={"Host": f"{site or site_of(CONTROL_ID)}:{port}"}
	)
	try:
		with urllib.request.urlopen(request, timeout=5) as response:
			return response.status == 200 and b"pong" in response.read()
	except (urllib.error.URLError, OSError):
		return False


def urls(control_id=CONTROL_ID, company_ids=COMPANY_IDS):
	lines = [f"Control (Platform Admin): http://{site_of(control_id)}:{PORT}/sellos"]
	for tenant_id in company_ids:
		lines.append(f"Company: http://{site_of(tenant_id)}:{PORT}/sellos")
	return "\n".join(lines)


def status_report(control_id=CONTROL_ID, company_ids=COMPANY_IDS):
	lines = []
	for tenant_id in (control_id, *company_ids):
		site = site_of(tenant_id)
		lines.append(
			f"{site}: site {'present' if _site_exists(site) else 'MISSING'}, "
			f"server {'answering' if serving(site=site) else 'not answering'} on {PORT}"
		)
	return "\n".join(lines)


def main(argv=None):
	argv = list(sys.argv[1:] if argv is None else argv)
	usage = (
		"usage: python -m sellos.testing.demo seed | migrate | reset | drop | status | urls"
		" [--control demo<id>] [--company demo<id> ...]"
	)
	if not argv or argv[0] not in ("seed", "migrate", "reset", "drop", "status", "urls"):
		print(usage, file=sys.stderr)
		return 2
	action, rest = argv[0], argv[1:]
	control, companies = CONTROL_ID, []
	while rest:
		if rest[0] == "--control" and len(rest) > 1:
			control, rest = rest[1], rest[2:]
		elif rest[0] == "--company" and len(rest) > 1:
			companies.append(rest[1])
			rest = rest[2:]
		else:
			print(usage, file=sys.stderr)
			return 2
	companies = tuple(companies) or COMPANY_IDS
	try:
		for tenant_id in (control, *companies):
			check_demo_id(tenant_id)
		if action == "seed":
			seed(control, companies)
		elif action == "migrate":
			migrate_all(control, companies)
		elif action == "reset":
			reset(control, companies)
		elif action == "drop":
			drop_all(control, companies)
		elif action == "status":
			print(status_report(control, companies))
		else:
			print(urls(control, companies))
	except DemoRefused as e:
		print(str(e), file=sys.stderr)
		return 2
	except DemoSeedFailed as e:
		print(f"DEMO SEED FAILED: {e}", file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
