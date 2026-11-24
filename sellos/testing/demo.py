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
COMPANY_IDS = ("demoalpha", "demobeta")
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

# One entry per company: its name, city, the short word in its sign in addresses and its leads.
# Each lead: name, type, phone, email, city, source, stage, consent, agent (0, 1 or None for the
# partner), requirements (budget from and to in lakh, configurations, property type, localities,
# purpose, timeline, possession), the days since the first contact.
COMPANIES = (
	{
		"name": "Skyline Realty",
		"city": "Mumbai",
		"word": "skyline",
		"leads": (
			(
				"Rohan Mehta",
				"Buyer",
				"+91 98200 11122",
				"rohan.mehta@example.com",
				"Mumbai",
				"Website",
				"New",
				"unknown",
				0,
				(
					80,
					120,
					["2 BHK"],
					"Apartment",
					["Andheri West", "Goregaon"],
					"End use",
					"Within 3 months",
					"Ready",
				),
				1,
			),
			(
				"Priya Nair",
				"Buyer",
				"+91 98765 43210",
				"priya.nair@example.com",
				"Thane",
				"Facebook",
				"Consent pending",
				"unknown",
				1,
				(
					60,
					90,
					["1 BHK", "2 BHK"],
					"Apartment",
					["Thane West"],
					"End use",
					"3 to 6 months",
					"Under construction",
				),
				2,
			),
			(
				"Aarav Shah",
				"Investor",
				"+91 98330 55501",
				"aarav.shah@example.com",
				"Mumbai",
				"Referral",
				"Contacted",
				"consented",
				0,
				(
					150,
					250,
					["3 BHK"],
					"Apartment",
					["Worli", "Lower Parel"],
					"Investment",
					"Immediate",
					"Ready",
				),
				5,
			),
			(
				"Sunita Deshpande",
				"Buyer",
				"+91 99870 22314",
				"sunita.d@example.com",
				"Navi Mumbai",
				"Portal",
				"Qualified",
				"consented",
				1,
				(
					70,
					100,
					["2 BHK", "3 BHK"],
					"Apartment",
					["Kharghar", "Panvel"],
					"End use",
					"Within 3 months",
					"Any",
				),
				9,
			),
			(
				"Vikram Singhania",
				"NRI",
				"+971 50 123 4567",
				"vikram.s@example.com",
				"Dubai",
				"Channel partner",
				"Site visit booked",
				"consented",
				None,
				(
					200,
					350,
					["3 BHK", "4 BHK and above"],
					"Villa",
					["Juhu", "Bandra West"],
					"Investment",
					"3 to 6 months",
					"Ready",
				),
				14,
			),
			(
				"Neha Kulkarni",
				"Buyer",
				"+91 98190 77654",
				"neha.k@example.com",
				"Mumbai",
				"Walk in",
				"Site visit done",
				"consented",
				0,
				(90, 130, ["2 BHK"], "Apartment", ["Powai"], "End use", "Immediate", "Ready"),
				18,
			),
			(
				"Imran Qureshi",
				"Buyer",
				"+91 98920 11876",
				"imran.q@example.com",
				"Mumbai",
				"Website",
				"Negotiation",
				"consented",
				1,
				(
					110,
					160,
					["3 BHK"],
					"Apartment",
					["Bandra East", "Kurla"],
					"End use",
					"Within 3 months",
					"Under construction",
				),
				24,
			),
			(
				"Kavita Rao",
				"Buyer",
				"+91 98210 99087",
				"kavita.rao@example.com",
				"Mumbai",
				"Referral",
				"Booking",
				"consented",
				0,
				(95, 125, ["2 BHK"], "Apartment", ["Malad"], "End use", "Immediate", "Ready"),
				30,
			),
			(
				"Manish Gupta",
				"Investor",
				"+91 98700 31245",
				"manish.g@example.com",
				"Mumbai",
				"Channel partner",
				"Closed won",
				"consented",
				None,
				(300, 450, ["4 BHK and above"], "Apartment", ["Worli"], "Investment", "Immediate", "Ready"),
				45,
			),
			(
				"Deepa Iyer",
				"Buyer",
				"+91 98336 40021",
				"deepa.iyer@example.com",
				"Mumbai",
				"Bought list",
				"Closed lost",
				"optedout",
				1,
				(50, 70, ["1 BHK"], "Apartment", ["Dadar"], "End use", "Over 6 months", "Any"),
				40,
			),
			(
				"Farhan Ali",
				"Buyer",
				"+91 98201 66789",
				"farhan.ali@example.com",
				"Mumbai",
				"Missed call",
				"Nurture",
				"dnd",
				0,
				(
					70,
					95,
					["2 BHK"],
					"Apartment",
					["Chembur"],
					"End use",
					"Over 6 months",
					"Under construction",
				),
				60,
			),
			(
				"Rohan Mehta",
				"Buyer",
				"098200 11122",
				"rohan.m.work@example.com",
				"Mumbai",
				"Portal",
				"New",
				"expired",
				1,
				(75, 110, ["2 BHK"], "Apartment", ["Andheri East"], "End use", "Within 3 months", "Ready"),
				3,
			),
			(
				"Anjali Verma",
				"Seller",
				"+91 98230 45012",
				"priya.nair@example.com",
				"Thane",
				"Walk in",
				"Contacted",
				"dnd",
				0,
				(None, None, [], "Plot", ["Thane West"], "Investment", "", "Any"),
				12,
			),
		),
	},
	{
		"name": "Greenfield Homes",
		"city": "Pune",
		"word": "greenfield",
		"leads": (
			(
				"Siddharth Joshi",
				"Buyer",
				"+91 98220 31001",
				"sid.joshi@example.com",
				"Pune",
				"Website",
				"New",
				"unknown",
				0,
				(55, 75, ["2 BHK"], "Apartment", ["Baner", "Aundh"], "End use", "Within 3 months", "Ready"),
				1,
			),
			(
				"Meera Kulkarni",
				"Buyer",
				"+91 98500 42002",
				"meera.k@example.com",
				"Pune",
				"Facebook",
				"Consent pending",
				"unknown",
				1,
				(
					40,
					60,
					["1 BHK", "2 BHK"],
					"Apartment",
					["Hinjewadi"],
					"End use",
					"3 to 6 months",
					"Under construction",
				),
				3,
			),
			(
				"Aditya Patil",
				"Investor",
				"+91 98900 53003",
				"aditya.patil@example.com",
				"Pune",
				"Referral",
				"Contacted",
				"consented",
				0,
				(
					120,
					200,
					["3 BHK"],
					"Villa",
					["Koregaon Park", "Kalyani Nagar"],
					"Investment",
					"Immediate",
					"Ready",
				),
				6,
			),
			(
				"Shweta Bhosale",
				"Buyer",
				"+91 98811 64004",
				"shweta.b@example.com",
				"Pimpri",
				"Portal",
				"Qualified",
				"consented",
				1,
				(45, 65, ["2 BHK"], "Apartment", ["Wakad"], "End use", "Within 3 months", "Any"),
				8,
			),
			(
				"Karan Malhotra",
				"NRI",
				"+1 415 555 0142",
				"karan.m@example.com",
				"San Jose",
				"Channel partner",
				"Site visit booked",
				"consented",
				None,
				(
					150,
					220,
					["3 BHK", "4 BHK and above"],
					"Villa",
					["Koregaon Park"],
					"Investment",
					"3 to 6 months",
					"Ready",
				),
				13,
			),
			(
				"Ritu Sharma",
				"Buyer",
				"+91 98230 75005",
				"ritu.sharma@example.com",
				"Pune",
				"Walk in",
				"Site visit done",
				"consented",
				0,
				(65, 85, ["2 BHK", "3 BHK"], "Apartment", ["Kothrud"], "End use", "Immediate", "Ready"),
				17,
			),
			(
				"Nikhil Deshmukh",
				"Buyer",
				"+91 99220 86006",
				"nikhil.d@example.com",
				"Pune",
				"Website",
				"Negotiation",
				"consented",
				1,
				(
					80,
					110,
					["3 BHK"],
					"Apartment",
					["Viman Nagar"],
					"End use",
					"Within 3 months",
					"Under construction",
				),
				22,
			),
			(
				"Pooja Chavan",
				"Buyer",
				"+91 98230 97007",
				"pooja.c@example.com",
				"Pune",
				"Referral",
				"Booking",
				"consented",
				0,
				(50, 70, ["2 BHK"], "Apartment", ["Undri"], "End use", "Immediate", "Ready"),
				28,
			),
			(
				"Rajesh Kamat",
				"Investor",
				"+91 98600 18008",
				"rajesh.kamat@example.com",
				"Pune",
				"Channel partner",
				"Closed won",
				"consented",
				None,
				(
					200,
					300,
					["4 BHK and above"],
					"Villa",
					["Boat Club Road"],
					"Investment",
					"Immediate",
					"Ready",
				),
				50,
			),
			(
				"Lata Pawar",
				"Buyer",
				"+91 98220 29009",
				"lata.pawar@example.com",
				"Pune",
				"Bought list",
				"Closed lost",
				"optedout",
				1,
				(30, 45, ["1 BHK"], "Apartment", ["Hadapsar"], "End use", "Over 6 months", "Any"),
				44,
			),
			(
				"Tushar Gaikwad",
				"Buyer",
				"+91 98500 30010",
				"tushar.g@example.com",
				"Pune",
				"Missed call",
				"Nurture",
				"dnd",
				0,
				(
					45,
					60,
					["2 BHK"],
					"Apartment",
					["Kharadi"],
					"End use",
					"Over 6 months",
					"Under construction",
				),
				65,
			),
			(
				"Siddharth Joshi",
				"Buyer",
				"098220 31001",
				"sid.j.office@example.com",
				"Pune",
				"Portal",
				"New",
				"expired",
				1,
				(55, 80, ["2 BHK"], "Apartment", ["Balewadi"], "End use", "Within 3 months", "Ready"),
				4,
			),
			(
				"Anita Joshi",
				"Seller",
				"+91 98220 41011",
				"meera.k@example.com",
				"Pune",
				"Walk in",
				"Contacted",
				"dnd",
				0,
				(None, None, [], "Shop", ["Camp"], "Investment", "", "Any"),
				11,
			),
		),
	},
)


class DemoRefused(RuntimeError):
	"""The demo code was pointed at a site that is not a demo site."""


class DemoSeedFailed(RuntimeError):
	"""One or more seed steps failed on a site. Names every step and its error."""


# The steps of this process's seed that failed, as {"step", "error"}. seed_company returns them, and seed()
# raises DemoSeedFailed for them after every site has been tried, so a failure is never just a missing section.
STEP_FAILURES = []


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
	return {"site": frappe.local.site, "users": [PLATFORM_ADMIN_EMAIL]}


def _addr(role_word, company_word):
	return f"{role_word}.{company_word}@{EMAIL_DOMAIN}"


def company_users(index):
	"""(email, first name, role) of the company's sign ins, in the order docs/DEMO.md lists them."""
	data = COMPANIES[index % len(COMPANIES)]
	word, name = data["word"], data["name"]
	return [
		(_addr("admin", word), f"{name} Admin", COMPANY_ADMIN),
		(_addr("agent1", word), "Asha Agent", AGENT),
		(_addr("agent2", word), "Bilal Agent", AGENT),
		(_addr("partner", word), "Chitra Partner", CHANNEL_PARTNER),
		(_addr("client", word), "Dev Client", CLIENT),
	]


def _ensure_client(row, owner):
	import frappe

	name, kind, phone, email, city = row[0], row[1], row[2], row[3], row[4]
	existing = frappe.db.get_value("Client", {"client_name": name, "email": email}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Client",
			"client_name": name,
			"client_type": kind,
			"phone": phone if not phone.startswith("+971") and not phone.startswith("+1") else "",
			"overseas_phone": phone if phone.startswith("+971") or phone.startswith("+1") else "",
			"email": email,
			"city": city,
			"country_of_residence": {"Dubai": "United Arab Emirates", "San Jose": "United States"}.get(city),
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.set_value("Client", doc.name, "owner", owner, update_modified=False)
	return doc.name


def _requirements(spec):
	low, high, configurations, property_type, localities, purpose, timeline, possession = spec
	values = {
		"configuration": configurations,
		"property_type": property_type,
		"preferred_localities": localities,
		"purpose": purpose,
		"possession": possession,
	}
	if low:
		values["budget_from"] = low * 100000
	if high:
		values["budget_to"] = high * 100000
	if timeline:
		values["timeline"] = timeline
	return values


def _consent(lead, kind, days):
	import frappe
	from frappe.utils import add_days, add_months, now_datetime

	from sellos.crm import consent

	if kind == "consented":
		frappe.get_doc(
			{
				"doctype": "Consent Record",
				"lead": lead,
				"basis": "Consent",
				"recorded_on": add_days(now_datetime(), -days),
				"evidence_link": f"https://{EMAIL_DOMAIN}/consent/{lead}",
			}
		).insert(ignore_permissions=True)
	elif kind == "expired":
		# An Application basis lapses after three months, so a record from six months ago is not live.
		frappe.get_doc(
			{
				"doctype": "Consent Record",
				"lead": lead,
				"basis": "Application",
				"recorded_on": add_months(now_datetime(), -6),
				"evidence_link": f"https://{EMAIL_DOMAIN}/application/{lead}",
			}
		).insert(ignore_permissions=True)
	elif kind == "optedout":
		consent.record_opt_out(lead, "WhatsApp", on=add_days(now_datetime(), -max(days - 2, 0)))
	elif kind == "dnd":
		consent.record_dnd_result(lead, 1)
	consent.sync_lead_status(lead)


def _ensure_lead(row, client, users, admin):
	import frappe
	from frappe.utils import add_days, now_datetime

	from sellos.crm import pipeline

	stage, kind, agent_index, spec, days = row[6], row[7], row[8], row[9], row[10]
	existing = frappe.db.get_value("Lead", {"client": client, "source": row[5]}, "name")
	if existing:
		return existing, False
	owner = users["partner"] if agent_index is None else users["agents"][agent_index]
	values = {"doctype": "Lead", "client": client, "source": row[5], "assigned_to": owner}
	values.update(_requirements(spec))
	doc = frappe.get_doc(values)
	doc.flags.ignore_permissions = True
	doc.insert()
	# The partner sees the leads it owns and the Agents the ones assigned to them (sellos.access.lead_permissions).
	frappe.db.set_value("Lead", doc.name, "owner", owner, update_modified=False)
	_consent(doc.name, kind, days)
	if stage != pipeline.first_stage():
		pipeline.move_lead(doc.name, stage, lost_reason="Budget too low")  # SOS-P1-21, used on a Lost stage
	created = add_days(now_datetime(), -days)
	frappe.db.set_value("Lead", doc.name, "creation", created, update_modified=False)
	return doc.name, True


def _activities(lead, agent, stage_index, days):
	import frappe
	from frappe.utils import add_days, now_datetime

	if frappe.db.exists("Lead Activity", {"lead": lead}):
		return
	notes = [
		("Call", "First call. Asked for a callback in the evening."),
		("WhatsApp", "Sent the brochure and the price sheet."),
		("Meeting", "Met at the sales office. Wants a second site visit with family."),
	]
	for i, (kind, text) in enumerate(notes[: 1 + min(stage_index, 2)]):
		frappe.get_doc(
			{
				"doctype": "Lead Activity",
				"lead": lead,
				"activity_type": kind,
				"activity_date": add_days(now_datetime(), -max(days - i * 2, 0)),
				"notes": text,
			}
		).insert(ignore_permissions=True)


def _tasks_and_visits(lead, agent, stage, days, data):
	import frappe
	from frappe.utils import add_days, now_datetime, today

	if stage in ("Qualified", "Contacted") and not frappe.db.exists("Lead Task", {"lead": lead}):
		frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": lead,
				"title": "Call back with the revised price",
				"due_date": add_days(today(), -1 if stage == "Contacted" else 2),
				"status": "Open",
				"assigned_to": agent,
			}
		).insert(ignore_permissions=True)
	if stage in ("Site visit booked", "Site visit done") and not frappe.db.exists(
		"Site Visit", {"lead": lead}
	):
		frappe.get_doc(
			{
				"doctype": "Site Visit",
				"lead": lead,
				"project_name": _market(data)["visit_projects"][0 if stage == "Site visit booked" else 1],
				"visit_datetime": add_days(now_datetime(), 2 if stage == "Site visit booked" else -3),
				"status": "Scheduled" if stage == "Site visit booked" else "Done",
			}
		).insert(ignore_permissions=True)


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


def seed_company(index=0):
	"""On a company site: users, sources, stages, clients, leads in all 11 stages, consent, support grants.
	Safe to run again: every record is looked up first."""
	import frappe

	from sellos.access.roles import ensure_roles
	from sellos.crm import call_outcomes, lead_sources, pipeline

	site = check_demo_site()
	del STEP_FAILURES[:]
	data = COMPANIES[int(index) % len(COMPANIES)]
	ensure_roles()
	pipeline.ensure_default_stages()
	lead_sources.ensure_default_sources()
	call_outcomes.ensure_defaults()  # SOS-P1-21: a lead moved to Closed lost records a reason
	for extra, enabled in (("Hoarding campaign", 1), ("Old newspaper ad", 0)):
		if not frappe.db.exists("Lead Source", extra):
			frappe.get_doc({"doctype": "Lead Source", "source_name": extra, "enabled": enabled}).insert(
				ignore_permissions=True
			)

	settings = frappe.get_single("SellOS Settings")
	settings.company_name = data["name"]
	settings.city = data["city"]
	settings.contact_email = f"hello@{data['word']}.{EMAIL_DOMAIN}"
	settings.setup_complete = 1
	settings.save(ignore_permissions=True)

	_ensure_user(PLATFORM_ADMIN_EMAIL, "Demo Platform Admin", [PLATFORM_ADMIN])
	emails = {}
	for email, first_name, role in company_users(index):
		_ensure_user(email, first_name, [role])
		emails.setdefault(role, []).append(email)
	users = {
		"admin": emails[COMPANY_ADMIN][0],
		"agents": emails[AGENT],
		"partner": emails[CHANNEL_PARTNER][0],
	}

	stage_order = [s["stage_name"] for s in pipeline.DEFAULT_STAGES]
	made = 0
	for row in data["leads"]:
		client = _ensure_client(row, users["admin"])
		lead, new = _ensure_lead(row, client, users, users["admin"])
		made += 1 if new else 0
		agent = users["partner"] if row[8] is None else users["agents"][row[8]]
		_activities(lead, agent, stage_order.index(row[6]), row[10])
		_tasks_and_visits(lead, agent, row[6], row[10], data)
	_support_grants(users["admin"])
	_seed_features(index, data, users)
	frappe.db.commit()  # nosemgrep  bench execute commits too
	return {
		"site": site,
		"leads_made": made,
		"leads": frappe.db.count("Lead"),
		"failed_steps": list(STEP_FAILURES),
	}


# --- Every feature built so far (SOS-DEMO-2) ---------------------------------------------------------
# The demo's content is realistic (sellos/testing/demo_data.py): Mumbai and Pune projects, partner firms,
# deals, commission payouts and WhatsApp conversations, built through the production APIs further down. The
# regression seed's "Regression ..." records are not used here. Everything below is safe to run again.

SALES_PASSWORD_WORD = "sales"
DEMO_TELEPHONY_ID = "FAKEOK-DEMO-NOT-A-REAL-KEY"  # FAKEOK: the fake provider accepts it
DEMO_TELEPHONY_TOKEN = "fake-demo-token-not-a-real-key"
DEMO_CONSENT_WORDING = (
	"I agree that {company} may call, WhatsApp and email me about properties that match my needs. "
	"I can withdraw this at any time."
)
# Calls for the call reports: (client index into the company's leads, purpose, provider state, seconds,
# cost in paise, days ago, agent index). Spread over 30 days, two agents, two purposes.
DEMO_CALL_PLAN = (
	(2, "Service", "completed", 185, 420, 1, 0),
	(3, "Service", "completed", 96, 230, 2, 1),
	(5, "Transactional", "completed", 310, 700, 3, 0),
	(6, "Service", "no-answer", 0, 0, 4, 1),
	(7, "Transactional", "completed", 142, 330, 6, 1),
	(4, "Service", "busy", 0, 0, 8, 0),
	(8, "Transactional", "completed", 410, 900, 11, 0),
	(2, "Service", "completed", 75, 180, 14, 1),
	(3, "Service", "failed", 0, 0, 17, 0),
	(5, "Service", "completed", 260, 580, 21, 1),
	(6, "Transactional", "completed", 55, 130, 24, 0),
	(7, "Service", "no-answer", 0, 0, 27, 1),
	(8, "Service", "completed", 330, 740, 29, 0),
)


def sales_manager_email(word):
	return f"{SALES_PASSWORD_WORD}.{word}@{EMAIL_DOMAIN}"


def _as(email):
	"""Run as a user, then go back (the regression seed's own helper, so the demo holds no set_user)."""
	from sellos.tests import ui_fixtures

	return ui_fixtures._as_user(email)


def _lead_of(data, row_index):
	import frappe

	row = data["leads"][row_index]
	client = frappe.db.get_value("Client", {"client_name": row[0], "email": row[3]}, "name")
	return frappe.db.get_value("Lead", {"client": client}, "name") if client else None


def _seed_features(index, data, users):
	import frappe

	admin, agents = users["admin"], users["agents"]
	frappe.db.set_single_value(
		"SellOS Settings", "consent_wording", DEMO_CONSENT_WORDING.format(company=data["name"])
	)
	_seed_telephony_demo(index, admin)
	_seed_sales_team(data, admin, agents)
	_seed_do_not_call(admin)
	frappe.db.commit()  # nosemgrep  so a failed step below rolls back only itself
	_isolated("inventory", _seed_demo_inventory, data, users)
	_isolated("partners", _seed_demo_partners, data, users)
	_isolated("enquiries", _seed_demo_enquiries, data)
	_isolated("sellers", _seed_demo_sellers, data, users)
	_isolated("deals and commission", _seed_demo_deals, data, users)
	_isolated("whatsapp", _seed_demo_whatsapp, data, users)
	_seed_calls(data, agents)
	_seed_agent_work(data, agents)
	_isolated("visits and follow ups", _seed_demo_visits_and_follow_ups, data, users)


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


def _seed_sales_team(data, admin, agents):
	"""A Sales Manager and a team holding both agents, so Teams and the Team report show data."""
	import frappe

	from sellos.access import teams

	manager = sales_manager_email(data["word"])
	_ensure_user(manager, f"{data['name']} Sales Manager", [SALES_MANAGER])
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


def _seed_calls(data, agents):
	"""Calls through the fake provider and the production call functions, with the provider's last event
	setting state, seconds and cost, spread over 30 days. A company that has any Call Log is left alone."""
	import frappe
	from frappe.utils import add_days, now_datetime

	from sellos.telephony import call_log
	from sellos.telephony.base import CallEvent, ProviderError

	if frappe.db.count("Call Log"):
		return
	for row, purpose, state, seconds, paise, days_ago, who in DEMO_CALL_PLAN:
		lead = _lead_of(data, row)
		if not lead:
			continue
		try:
			log = call_log.place_logged_call(lead, purpose)["log"]
		except ProviderError:
			continue  # an overseas number has no Indian route: that lead has no call
		if not log:
			continue
		call_id = frappe.db.get_value("Call Log", log, "call_id")
		call_log.apply_event(CallEvent(call_id, state, duration=seconds), cost=paise, cost_unit="paise")
		frappe.db.set_value(
			"Call Log", log, {"started_on": add_days(now_datetime(), -days_ago), "agent": agents[who]}
		)


def _seed_agent_work(data, agents):
	"""What the bell and the Today screen read: open follow ups (one overdue, one soon, one later), a site
	visit tomorrow for each agent, a lead assigned notification for each assigned lead, and one run of the
	scheduler's notification functions. Safe to run again: a follow up or visit that exists is left alone."""
	import frappe
	from frappe.utils import add_days, add_to_date, get_datetime, now_datetime, today

	from sellos.crm import api as crm
	from sellos.crm import notifications

	plan = (
		(0, 2, "Call back about the revised price", add_to_date(now_datetime(), hours=-3)),
		(0, 5, "Ring back about the booking amount", add_to_date(now_datetime(), minutes=15)),
		(1, 3, "Send the payment plan", add_to_date(now_datetime(), hours=-1)),
		(1, 6, "Confirm the site visit with the family", add_to_date(now_datetime(), hours=2)),
		(1, 1, "Follow up on the brochure", add_to_date(now_datetime(), days=1)),
	)
	for agent_index, row, title, when in plan:
		lead = _lead_of(data, row)
		if not lead or frappe.db.exists("Lead Task", {"lead": lead, "title": title}):
			continue
		with _as(agents[agent_index]):
			crm.save_task(
				values={
					"lead": lead,
					"title": title,
					"due_at": when,
					"status": "Open",
					"assigned_to": agents[agent_index],
				}
			)
	market = _market(data)
	# (agent, lead row, project, hour, the name an earlier seed gave it, so a site made before is not doubled)
	visits = (
		(0, 5, market["visit_projects"][2], 11, "Tomorrow tour"),
		(1, 6, market["visit_projects"][0], 15, "Tomorrow walkthrough"),
	)
	for agent_index, row, project, hour, earlier in visits:
		lead = _lead_of(data, row)
		if not lead or frappe.db.exists(
			"Site Visit", {"lead": lead, "project_name": ["in", [project, earlier]]}
		):
			continue
		stage = frappe.db.get_value("Lead", lead, "stage")
		with _as(agents[agent_index]):
			crm.save_site_visit(
				values={
					"lead": lead,
					"project_name": project,
					"visit_datetime": add_to_date(get_datetime(add_days(today(), 1)), hours=hour),
					"status": "Scheduled",
				}
			)
			# Booking moves a lead to Site visit booked. The demo keeps the stage the lead was seeded in.
			if frappe.db.get_value("Lead", lead, "stage") != stage:
				crm.move_lead_stage(lead, stage)
	for row in range(len(data["leads"])):
		lead = _lead_of(data, row)
		owner = frappe.db.get_value("Lead", lead, "assigned_to") if lead else None
		if owner in agents and row < 6:
			notifications.notify(
				owner,
				notifications.LEAD_ASSIGNED,
				"Lead assigned to you",
				f"{frappe.db.get_value('Lead', lead, 'lead_title')} was assigned to you.",
				lead=lead,
				dedupe_key=f"demo-assigned-{lead}",
			)
	notifications.notify_follow_ups()
	notifications.notify_site_visits()


# --- Realistic content: inventory, partners, deals, commission, WhatsApp (replaces the "Regression" names) --
# Everything below reads sellos/testing/demo_data.py and goes through the production APIs, as the person who
# would do it. Each function looks a record up first, so running it again adds nothing. Each runs on its own
# (`_isolated`): if one fails, the others still run and the failure is printed, so one bad record never stops
# `scripts/demo.sh update`.


def _market(data):
	from sellos.testing import demo_data

	return demo_data.MARKET[data["word"]]


def demo_seed(kind, n):
	"""The phone seed (not the number) for sellos.tests.phones.in_mobile, one range per kind."""
	from sellos.testing import demo_data

	return demo_data.PHONE_SEEDS[kind] + n


def _seed(kind, n):
	"""A fake phone number for the demo, from sellos.tests.phones, never written by hand."""
	from sellos.tests import phones

	return phones.in_mobile(demo_seed(kind, n))


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


def _project_name_of(market, index):
	return market["projects"][index]["name"]


def _price_list(title, rate, on="2025-01-01"):
	"""A dated price list: the project's base rate per sq ft, a floor rise above floor 4 and three charges."""
	return {
		"title": title,
		"effective_from": on,
		"base_rate": rate,
		"floor_rise_rate": 100,
		"floor_rise_from_floor": 4,
		"charges": [
			{
				"charge_type": "Preferred location",
				"charge_name": "Garden facing",
				"basis": "Rate per sq ft",
				"value": 150,
			},
			{"charge_type": "Parking", "charge_name": "Covered parking", "basis": "Amount", "value": 400000},
			{
				"charge_type": "Other",
				"charge_name": "Development charges",
				"basis": "Amount",
				"value": 250000,
				"always_apply": 1,
			},
		],
	}


def _seed_demo_inventory(data, users):
	"""Developers, projects with towers, units and holds, a price list, payment plans, a cost sheet, resale
	properties and published listings."""
	import frappe

	from sellos.inventory import api, cost_sheet, holds, listings, pricing, structure

	market = _market(data)
	admin, agent = users["admin"], users["agents"][0]
	first = _project_name_of(market, 0)
	if frappe.db.exists("Project", {"project_name": first}):
		return
	with _as(admin):
		for name, person, email in market["developers"]:
			if not frappe.db.exists("Developer", name):
				api.save_developer({"developer_name": name, "contact_person": person, "email": email})
		pricing.save_cost_settings(6, 1, 5)
		projects = []
		for spec in market["projects"]:
			developer = market["developers"][spec["developer"]][0]
			project = api.save_project(
				{
					"project_name": spec["name"],
					"developer": developer,
					"rera_number": spec["rera"],
					"city": spec["city"],
					"locality": spec["locality"],
					"project_status": spec["status"],
				}
			)["name"]
			projects.append(project)
			if "tower" in spec:
				tower_name, floor, ranges, area, configuration = spec["tower"]
				for amenity in spec["amenities"]:
					structure.save_amenity(amenity)
				structure.save_project_details(project, spec["possession"], list(spec["amenities"]))
				tower = structure.add_tower(project, tower_name, f"{floor} to {floor + len(ranges) - 1}")[
					"name"
				]
				for offset, (low, high) in enumerate(ranges):
					structure.generate_floor_units(
						tower, floor + offset, f"{low} to {high}", area, configuration
					)
				units = {u["unit_number"]: u["name"] for u in api.get_project(project)["units"]}
				for number in spec["three_bhk"]:
					api.save_unit({"configuration": "3 BHK", "carpet_area": 905}, name=units[number])
			else:
				for number, configuration, floor, area, parking in spec["units"]:
					api.save_unit(
						{
							"project": project,
							"unit_number": number,
							"configuration": configuration,
							"floor": floor,
							"carpet_area": area,
							"parking": parking,
						}
					)
			pricing.save_price_list(project, _price_list(f"{spec['name']} price list 2025", spec["rate"]))
		plan = pricing.save_payment_plan(
			projects[0],
			{
				"plan_name": "Construction linked 20:30:50",
				"plan_type": "Construction linked",
				"instalments": [
					{"label": "On booking", "due_on": "On booking", "percent": 20},
					{"label": "On the 8th floor slab", "due_on": "On the 8th floor slab", "percent": 30},
					{"label": "On possession", "due_on": "On possession", "percent": 50},
				],
			},
		)["name"]
		pricing.save_payment_plan(
			projects[1],
			{
				"plan_name": "Ready home 10:90",
				"plan_type": "Time linked",
				"instalments": [
					{"label": "Booking amount", "days_after_booking": 0, "percent": 10},
					{"label": "At agreement, 30 days after", "days_after_booking": 30, "percent": 90},
				],
			},
		)
		holds.block_unit(_unit_of(projects, market, market["block"]), market["block"]["reason"])
		sample_unit = _unit_of(
			projects, market, {"project": 0, "unit": market["projects"][0]["tower"][2][0][0]}
		)
	with _as(agent):
		cost_sheet.make_cost_sheet(sample_unit, plan, ["Garden facing"])
		hold = market["hold"]
		lead = _lead_of(data, hold["lead"])
		if lead:
			holds.hold_unit(_unit_of(projects, market, hold), lead)
		props = []
		for spec in market["properties"]:
			values = {k: v for k, v in spec.items() if k != "asking_price"}
			props.append(api.save_property(values)["name"])
		# Published listings: a unit of each of the first two projects, and the resale flats.
		for project_index, unit_number, title, price in _listing_plan(market):
			listing = listings.save_listing(
				{
					"title": title,
					"listing_type": "Primary",
					"unit": _unit_of(projects, market, {"project": project_index, "unit": unit_number}),
					"asking_price": price,
					"description": f"{title}. Registered with RERA, with a payment plan to suit.",
				}
			)["name"]
			listings.publish_listing(listing)
		for prop, spec in zip(props, market["properties"], strict=True):
			listing = listings.save_listing(
				{
					"title": spec["title"],
					"listing_type": "Direct",
					"property": prop,
					"asking_price": spec["asking_price"],
					"description": f"{spec['title']}. Society with 24 hour security and a lift.",
				}
			)["name"]
			listings.publish_listing(listing)


def _listing_plan(market):
	"""(project index, unit number, title, asking price) of the published primary listings."""
	out = []
	for index in (0, 1):
		spec = market["projects"][index]
		unit_number = spec["tower"][2][0][0] if "tower" in spec else spec["units"][0][0]
		area = spec["tower"][3] if "tower" in spec else spec["units"][0][3]
		configuration = spec["tower"][4] if "tower" in spec else spec["units"][0][1]
		price = int(area * spec["rate"])
		out.append((index, str(unit_number), f"{configuration} at {spec['name']}, {spec['locality']}", price))
	return out


def _unit_of(projects, market, ref):
	import frappe

	return frappe.db.get_value(
		"Unit", {"project": projects[ref["project"]], "unit_number": str(ref["unit"])}, "name"
	)


def _seed_demo_partners(data, users):
	"""The company's partner firm (the demo Channel Partner is its contact person), two more firms at other
	stages, the buyers the partner registers and the projects the company shares with its firms."""
	import frappe

	from sellos.access import partner_firms, partner_registrations
	from sellos.inventory import partner_shares
	from sellos.tests import ui_fixtures as fx
	from sellos.tests.files import tiny_pdf_base64

	market = _market(data)
	admin, partner = users["admin"], users["partner"]
	spec = market["partner"]
	if not frappe.db.exists("Channel Partner Firm", {"firm_name": spec["firm"]}):
		with _as(admin):
			doc = frappe.get_doc(
				{
					"doctype": "Channel Partner Firm",
					"firm_name": spec["firm"],
					"contact_user": partner,
					"contact_person": spec["person"],
					"email": partner,
				}
			).insert()
		with _as(partner):
			partner_firms.submit_partner_details(
				{"phone": _seed("partner", 0), "rera_number": spec["rera"], "pan": spec["pan"]}
			)
			partner_firms.upload_my_agreement("partner_agreement_signed.pdf", tiny_pdf_base64())
		with _as(admin):
			partner_firms.approve_partner_firm(doc.name)
	firm = frappe.db.get_value("Channel Partner Firm", {"firm_name": spec["firm"]}, "name")
	for offset, (name, stage, local) in enumerate(market["other_firms"], start=1):
		if not frappe.db.exists("Channel Partner Firm", {"firm_name": name}):
			fx._make_partner_firm(admin, name, f"{local}.{EMAIL_DOMAIN}", stage, demo_seed("partner", offset))
	for offset, (buyer, project, note, decision) in enumerate(market["registrations"], start=3):
		if frappe.db.exists("Partner Registration", {"buyer_name": buyer}):
			continue
		with _as(partner):
			result = partner_registrations.register_buyer(
				buyer, _seed("partner", offset), project, note, 1 if decision == "approve" else 0
			)
		code = result["registration"]["name"]
		with _as(admin):
			if decision == "approve":
				partner_registrations.approve_partner_registration(code)
			elif decision == "reject":
				partner_registrations.reject_partner_registration(code, "The buyer is not looking right now")
	names = [_project_name_of(market, i) for i in range(len(market["projects"]))]
	ids = [frappe.db.get_value("Project", {"project_name": n}, "name") for n in names]
	# Looked up by the demo's own projects, so shares an earlier seed made do not stop these.
	if all(ids) and not frappe.db.exists("Partner Share", {"project": ["in", ids]}):
		with _as(admin):
			partner_shares.share_project(ids[0], [firm], share_price_list=1)
			partner_shares.share_project(ids[1], "all")
			partner_shares.share_project(ids[2], [firm])
	return firm


def _seed_demo_deals(data, users):
	"""Deals in four stages with commission payouts for the partner firm: Paid, Approved, Due, and one deal
	whose split still waits for approval. Made by the Company Admin through the deal and commission methods."""
	import frappe
	from frappe.utils import add_days, today

	from sellos.inventory import commissions, deals

	market = _market(data)
	admin, agents = users["admin"], users["agents"]
	firm = frappe.db.get_value("Channel Partner Firm", {"firm_name": market["partner"]["firm"]}, "name")
	if not firm:
		return
	projects = [
		frappe.db.get_value("Project", {"project_name": spec["name"]}, "name") for spec in market["projects"]
	]
	with _as(admin):
		for project in projects:
			if project and not frappe.db.exists("Commission Rate", {"project": project}):
				commissions.save_commission_rate(
					{"project": project, "rate_type": "Percentage", "value": 2, "start_date": "2025-01-01"}
				)
		for spec in market["deals"]:
			row = data["leads"][spec["lead"]]
			client = frappe.db.get_value("Client", {"client_name": row[0], "email": row[3]}, "name")
			lead = _lead_of(data, spec["lead"])
			if not client or frappe.db.exists("Deal", {"client": client}):
				continue
			if "property" in spec:
				prop = frappe.db.get_value(
					"Property", {"title": market["properties"][spec["property"]]["title"]}
				)
				target = {"property": prop}
			else:
				target = {"unit": _unit_of(projects, market, spec)}
			if not next(iter(target.values())):
				continue
			commission = int(spec["price"] * 0.02)
			agent = agents[0 if row[8] in (None, 0) else 1]
			partner_percent = spec["partner"]
			splits = [{"party_type": "Agent", "agent": agent, "percent": 100 - 30 - partner_percent}]
			if partner_percent:
				splits.append(
					{"party_type": "Channel Partner", "partner_firm": firm, "percent": partner_percent}
				)
			splits.append({"party_type": "Company", "percent": 30})
			made = deals.save_deal(
				{
					"client": client,
					"lead": lead,
					**target,
					"price": spec["price"],
					"deal_date": str(add_days(today(), -spec["days"])),
					"commission_amount": commission,
					"splits": splits,
				}
			)["name"]
			if spec["approved"]:
				deals.approve_splits(made)
			payout = frappe.db.get_value("Commission Payout", {"deal": made, "partner_firm": firm})
			if payout and spec["payout"] in ("approved", "paid"):
				commissions.move_payout(payout, "Approved")
			if payout and spec["payout"] == "paid":
				commissions.move_payout(
					payout,
					"Paid",
					payment_reference=f"UTR2611{spec['days']:03d}{spec['lead']:02d}7781",
					paid_on=str(add_days(today(), -max(spec["days"] - 12, 1))),
				)


def _seed_demo_sellers(data, users):
	"""Two owners who want to sell: each a Seller lead with its property, one with a Draft Exclusive mandate
	and one with a Signed Open mandate and a dossier."""
	import base64

	import frappe

	from sellos.crm import api as crm
	from sellos.inventory import api, mandates
	from sellos.tests.files import tiny_pdf

	market = _market(data)
	admin, agent = users["admin"], users["agents"][0]
	pdf = base64.b64encode(tiny_pdf()).decode()
	for offset, spec in enumerate(market["sellers"]):
		if frappe.db.exists("Client", {"client_name": spec["name"]}):
			continue
		with _as(admin):
			client = crm.save_client(
				values={
					"client_name": spec["name"],
					"client_type": "Seller",
					"phone": _seed("seller", offset),
					"email": spec["email"],
					"city": spec["city"],
				}
			)
		with _as(agent):
			prop = api.save_property({**spec["property"], "property_type": "Apartment"})["name"]
		with _as(admin):
			lead = crm.save_lead(
				values={
					"client": client["name"],
					"pipeline": "Seller",
					"source": "Referral",
					"assigned_to": agent,
					"property": prop,
				}
			)["lead"]["name"]
		with _as(agent):
			crm.move_lead_stage(lead, "Seller Qualified")
			if spec["stage"] == "Seller Valuation shared":
				crm.move_lead_stage(lead, spec["stage"])
			kind, months, fee, signed = spec["mandate"]
			mandate = mandates.save_mandate(
				{"lead": lead, "mandate_type": kind, "term_months": months, "fee_percent": fee}
			)["name"]
			if signed:
				mandates.sign_mandate(mandate, "mandate_signed.pdf", pdf)
				mandates.add_dossier_note(mandate, "Access to the flat", "The caretaker holds the keys.")
				mandates.add_dossier_file(mandate, "Title deed", "title_deed.pdf", pdf)
			else:
				mandates.add_dossier_note(mandate, "Owner's reserve price", "The owner will not go below it.")


def _seed_demo_enquiries(data):
	"""Two leads from the enquiry page (one asks to be left alone) and one missed call, through the one
	lead intake. A number that already belongs to a client is left alone."""
	import frappe

	from sellos.crm import intake
	from sellos.crm.duplicates import normalise_phone
	from sellos.telephony import inbound
	from sellos.telephony.base import CallEvent

	market = _market(data)
	for offset, (name, stop) in enumerate(market["enquiries"]):
		phone = _seed("enquiry", offset)
		if frappe.db.exists("Client", {"phone_key": normalise_phone(phone)}):
			continue
		intake.take(
			phone=phone,
			source="Website",
			campaign="Enquiry page",
			kind="enquiry",
			reference=f"demo-enquiry-{data['word']}-{offset}",
			evidence={"page": "enquiry", "wording": DEMO_CONSENT_WORDING.format(company=data["name"])},
			name=name,
			notes="Sent the enquiry page.",
			stop_source=stop,
		)
	our_number = inbound.our_number()
	phone = _seed("enquiry", 5)
	if our_number and not frappe.db.exists("Client", {"phone_key": normalise_phone(phone)}):
		inbound.handle_missed_call(
			CallEvent(
				call_id=f"demo-missed-call-{data['word']}",
				state="no-answer",
				from_number=phone,
				to_number=our_number,
				direction="inbound",
			)
		)


DEMO_WHATSAPP_TOKEN = "FAKEOK-DEMO-WHATSAPP"  # FAKEOK: the fake provider accepts it
DEMO_WHATSAPP_SECRET = "demo-whatsapp-signing-secret"  # never a real secret


def _seed_demo_whatsapp(data, users):
	"""The company's WhatsApp number with a template, and five conversations through the production receive
	and send functions with the fake provider: a customer who writes in Hinglish and gets replies, one who
	opts in, one handed to a human, one who sends STOP, and one who gets a visit reminder template."""
	import frappe

	from sellos.tests import ui_fixtures as fx
	from sellos.whatsapp import conversations
	from sellos.whatsapp.base import InboundMessage, StatusEvent

	market = _market(data)
	spec = market["whatsapp"]
	admin, agent = users["admin"], users["agents"][0]
	fx._save_whatsapp_account(admin, spec["template"], token=DEMO_WHATSAPP_TOKEN, secret=DEMO_WHATSAPP_SECRET)
	for offset, customer in enumerate(spec["customers"]):
		name = customer["name"]
		if frappe.db.exists("Client", {"client_name": name}):
			continue
		phone = _seed("whatsapp", offset)
		lead = fx._whatsapp_customer(admin, agent, name, demo_seed("whatsapp", offset))
		sent = []
		for step, (kind, payload) in enumerate(customer["script"]):
			if kind == "in":
				conversations.receive(
					InboundMessage(f"wamid-demo-{data['word']}-{offset}-{step}", phone, payload, name=name)
				)
			elif kind == "out":
				with _as(agent):
					sent.append(conversations.send(lead, text=payload)["message"])
			elif kind == "template":
				with _as(agent):
					sent.append(
						conversations.send(lead, template=spec["template"], parameters=list(payload))[
							"message"
						]
					)
			elif kind == "handoff":
				with _as(agent):
					conversations.hand_off(
						frappe.db.get_value("WhatsApp Conversation", {"lead": lead}), None, payload
					)
		for message in [m for m in sent if m]:
			provider_id = frappe.db.get_value("WhatsApp Message", message, "provider_message_id")
			if provider_id:
				conversations.apply_status(StatusEvent(provider_id, "read" if offset == 0 else "delivered"))


def _seed_demo_visits_and_follow_ups(data, users):
	"""What the Home screen reads: three site visits TODAY (the lead's own agent, on the next demo update a new
	day gets new visits) and follow ups that are one and two days overdue. A visit moves its lead to Site visit
	booked, so the lead is put back on the stage it was seeded in."""
	import frappe
	from frappe.utils import add_days, add_to_date, get_datetime, now_datetime, today

	from sellos.crm import api as crm

	market = _market(data)
	agents = users["agents"]
	plan = ((2, 11, 0), (3, 15, 1), (6, 17, 1))  # lead row, hour, agent index
	day = get_datetime(today())
	for (row, hour, agent_index), project in zip(plan, market["visit_projects"], strict=True):
		lead = _lead_of(data, row)
		if not lead:
			continue
		if frappe.db.exists(
			"Site Visit",
			{
				"lead": lead,
				"project_name": project,
				"visit_datetime": ["between", [str(day), str(add_days(day, 1))]],
			},
		):
			continue
		stage = frappe.db.get_value("Lead", lead, "stage")
		with _as(agents[agent_index]):
			crm.save_site_visit(
				values={
					"lead": lead,
					"project_name": project,
					"visit_datetime": add_to_date(day, hours=hour),
					"status": "Scheduled",
				}
			)
			if frappe.db.get_value("Lead", lead, "stage") != stage:
				crm.move_lead_stage(lead, stage)
	late = (
		(7, 0, "Collect the token cheque for the booking", add_days(now_datetime(), -2)),
		(5, 0, "Send the revised cost sheet", add_days(now_datetime(), -1)),
		(1, 1, "Share the project brochure again", add_days(now_datetime(), -1)),
	)
	for row, agent_index, title, when in late:
		lead = _lead_of(data, row)
		if not lead or frappe.db.exists("Lead Task", {"lead": lead, "title": title}):
			continue
		with _as(agents[agent_index]):
			crm.save_task(
				values={
					"lead": lead,
					"title": title,
					"due_at": when,
					"status": "Open",
					"assigned_to": agents[agent_index],
				}
			)


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
