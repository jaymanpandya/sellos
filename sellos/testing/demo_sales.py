"""The demo's sales side: sellers and mandates, channel partners, deals and commission payouts (demo seed).

The third builder of a company seed, after inventory and crm. It reads ctx.leads, ctx.units, ctx.properties and
ctx.projects, and leaves ctx.sellers, ctx.mandates, ctx.partners, ctx.deals and ctx.payouts. Everything is made
through the production APIs (the same methods the screens call), looked up before it is created, so a second run
creates nothing.

The generator functions at the top are pure (no Frappe import, no clock): they take the random generator, the
region key and today, and return plain dicts that the unit tests read. `build(ctx)` is the Frappe side.
"""

import re
from datetime import timedelta

from sellos.testing import demo_names

# Phone seeds for sellos.tests.phones.in_mobile: one range per kind, far from the other builders' ranges.
SEEDS = {"seller": 70000, "firm": 70100, "registration": 70200, "client": 70300}

SELLERS = 25
FIRMS = 12
REGISTRATIONS = 24

LOCALITIES = {
	"bom": (
		"Andheri West",
		"Powai",
		"Bandra East",
		"Worli",
		"Thane",
		"Mulund",
		"Chembur",
		"Goregaon",
		"Borivali",
		"Navi Mumbai",
	),
	"amd": (
		"SG Highway",
		"Prahlad Nagar",
		"Bopal",
		"Shela",
		"Gota",
		"Satellite",
		"Thaltej",
		"Vastrapur",
		"South Bopal",
		"Science City",
	),
}

BUILDINGS = (
	"Sunrise Heights",
	"Lotus Residency",
	"Palm Court",
	"Green Meadows",
	"Silver Oak Apartments",
	"Blue Orchid Towers",
	"Marigold Villas",
	"Shanti Niwas",
	"Ocean Pearl",
	"Anand Kunj",
	"Jasmine Gardens",
	"Riverside Residency",
	"Maple Terrace",
	"Orchid Park",
	"Kesar Heights",
	"Tulsi Enclave",
	"Amber Court",
	"Harmony Towers",
	"Saffron Square",
	"Vasant Vihar Apartments",
	"Coral Bay Residency",
	"Neelkamal Heights",
	"Sapphire Arcade",
	"Dhruv Tara",
	"Lakeview Terraces",
	"Mohan Nivas",
	"Rajhans Residency",
	"Cedar Grove",
	"Krishna Kunj",
	"Pearl Plaza",
	"Gulmohar Park",
	"Evergreen Heights",
	"Aashirwad Apartments",
	"Vrindavan Towers",
	"Rose Wood Court",
	"Skyline Meadows",
	"Padmavati Heights",
	"Nilgiri Residency",
	"Ashiana Court",
	"Sai Darshan",
)

# BHK size: configuration, then the carpet area range in square feet.
APARTMENTS = (
	("1 BHK", 420, 560),
	("2 BHK", 700, 980),
	("3 BHK", 1050, 1500),
	("4 BHK", 1700, 2300),
)

# (seller stage, what the mandate is). 25 sellers: every seller stage, a mandate in every state.
#   draft: not signed yet. signed: signed and running. expired: signed, but its term has run out.
#   archived: signed, then archived.
SELLER_PLAN = (
	("New owner enquiry", "draft"),
	("New owner enquiry", "draft"),
	("Qualified", "draft"),
	("Qualified", "draft"),
	("Qualified", "draft"),
	("Valuation shared", "draft"),
	("Valuation shared", "draft"),
	("Valuation shared", "draft"),
	("Mandate proposed", "draft"),
	("Mandate proposed", "draft"),
	("Mandate proposed", "draft"),
	("Mandate proposed", "draft"),
	("Mandate signed", "signed"),
	("Mandate signed", "signed"),
	("Mandate signed", "signed"),
	("Listed", "signed"),
	("Listed", "signed"),
	("Listed", "signed"),
	("Listed", "signed"),
	("Offers received", "signed"),
	("Offers received", "signed"),
	("Sold", "signed"),
	("Nurture", "expired"),
	("Nurture", "expired"),
	("Closed lost", "archived"),
)
ENQUIRIES_BY_STAGE = {"Mandate signed": 1, "Listed": 3, "Offers received": 4, "Sold": 2}
SELLER_SOURCES = ("Referral", "Website", "Portal", "Walk in", "Facebook")
MANDATE_STATES = ("draft", "signed", "expired", "archived")

DOSSIER_NOTES = (
	("Access to the flat", "The caretaker holds the keys. Call him a day before a viewing."),
	("Owner's reserve price", "The owner will not go below it. Keep the figure away from buyers."),
	("Society formalities", "The society needs its NOC before a transfer. The secretary has the form."),
	("Loan on the property", "A home loan is still running. The owner will bring the foreclosure letter."),
	("Viewing times", "Weekday evenings after six and Saturday mornings suit the family."),
)
DOSSIER_FILES = (
	("Title deed", "title_deed.pdf"),
	("Society share certificate", "share_certificate.pdf"),
	("Property tax receipt", "property_tax_receipt.pdf"),
)
LOST_REASONS = ("No longer looking", "Other")

FIRM_SUFFIXES = (
	"Property Consultants",
	"Realty Partners",
	"Estate Agents",
	"Homes Advisory",
	"Realty Associates",
	"Property Hub",
	"Estate Advisors",
	"Realty Services",
)
# 7 approved (the first is the demo's own partner), 2 pending, 2 invited, 1 suspended.
FIRM_STATUSES = ("approved",) * 7 + ("pending",) * 2 + ("invited",) * 2 + ("suspended",)
SUSPEND_REASONS = ("The agreement was not renewed", "Two buyers were registered that the company already had")

# What the 24 registrations are: 5 Registered, 6 Approved, 4 Visited, 3 Booked, 3 Expired, 3 Rejected.
REGISTRATION_STATUSES = (
	("Registered",) * 5
	+ ("Approved",) * 6
	+ ("Visited",) * 4
	+ ("Booked",) * 3
	+ ("Expired",) * 3
	+ ("Rejected",) * 3
)
DAYS_BY_REGISTRATION = {
	"Registered": (0, 4),
	"Approved": (8, 40),
	"Visited": (20, 55),
	"Booked": (30, 60),
	"Expired": (110, 170),
	"Rejected": (5, 60),
}
REJECTIONS = (
	"The buyer is not looking right now",
	"The buyer is already with another agent",
	"The phone number does not reach the buyer",
)
CONFIGURATIONS = ("1 BHK", "2 BHK", "3 BHK", "4 BHK")

# A Company Admin's commission rates, a percentage of the agreement value, by project.
PROJECT_RATES = (2, 2.5, 1.5, 2, 3, 2)
HOLD_REASONS = (
	"The firm's agreement copy has not come in",
	"The buyer's second instalment is not received",
	"The firm's PAN needs to be checked",
	"The developer has not yet confirmed the booking",
)
CANCEL_REASONS = (
	"The buyer's home loan was not sanctioned",
	"The buyer chose a ready flat instead",
)

PAN_RE = re.compile(r"^[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]$")
MAHA_RERA_RE = re.compile(r"^A518000\d{5}$")
GUJARAT_RERA_RE = re.compile(r"^PR/GJ/AHMEDABAD/AGENT/AG\d{5}/\d{2}$")


def _slug(text):
	return re.sub(r"[^a-z0-9]+", "", text.lower())


def _email(first, last):
	return f"{_slug(first)}.{_slug(last)}@example.com"


def seller_plan(rng, region, today, used):
	"""The 25 sellers: a person, the property they own, the stage of their lead and the state of the mandate."""
	city = demo_names.REGIONS[region]["city"]
	people = demo_names.people(rng, region, SELLERS, used)
	stages = list(SELLER_PLAN)
	rng.shuffle(stages)
	buildings = rng.sample(BUILDINGS, SELLERS)
	rows = []
	for i, (person, (stage, state), building) in enumerate(zip(people, stages, buildings, strict=True)):
		rows.append(
			{
				"name": person["name"],
				"email": _email(person["first"], person["last"]),
				"phone_seed": SEEDS["seller"] + i,
				"city": city,
				"property": _seller_property(rng, region, i, building, city),
				"stage": stage,
				"source": rng.choice(SELLER_SOURCES),
				"agent_index": i % 4,
				"created_days": rng.randint(10, 150),
				"enquiries": ENQUIRIES_BY_STAGE.get(stage, 0),
				"lost_reason": rng.choice(LOST_REASONS) if stage == "Closed lost" else "",
				"mandate": _mandate_plan(rng, state),
			}
		)
	return rows


def _seller_property(rng, region, i, building, city):
	locality = rng.choice(LOCALITIES[region])
	if i in (7, 19):
		kind, config, low, high, floor = "Villa", "Villa", 2200, 4200, 0
		title = f"Villa, {building}, {locality}"
	elif i == 13:
		kind, config, low, high, floor = "Office", "Office", 600, 1400, rng.randint(2, 9)
		title = f"Office, {building}, {locality}"
	elif i == 22:
		kind, config, low, high, floor = "Shop", "Shop", 250, 600, 0
		title = f"Shop, {building}, {locality}"
	else:
		config, low, high = rng.choice(APARTMENTS)
		kind, floor = "Apartment", rng.randint(1, 22)
		title = f"{config}, {building}, {locality}"
	return {
		"title": title,
		"property_type": kind,
		"building_name": building,
		"city": city,
		"locality": locality,
		"address": f"{building}, {locality}, {city}",
		"configuration": config,
		"carpet_area": round(rng.randint(low, high), -1),
		"floor": floor,
		"parking": 0 if kind in ("Shop",) else rng.randint(1, 2),
	}


def _mandate_plan(rng, state):
	"""The terms of one mandate. A signed one is still running; an expired one has run past its term."""
	if state == "draft":
		term, ago = rng.choice((3, 6, 12)), rng.randint(0, 20)
	elif state == "signed":
		term = rng.choice((6, 9, 12))
		ago = rng.randint(10, min(150, term * 30 - 30))
	elif state == "expired":
		term, ago = 6, rng.randint(230, 420)
	else:
		term, ago = 6, rng.randint(60, 150)
	return {
		"state": state,
		"mandate_type": rng.choice(("Exclusive", "Exclusive", "Open")),
		"term_months": term,
		"fee_percent": rng.choice((1.0, 1.25, 1.5, 2.0)),
		"start_days_ago": ago,
		"notes": rng.sample(range(len(DOSSIER_NOTES)), 2),
		"files": rng.randint(1, 2),
	}


def client_seller_spec(rng, region, name, email):
	"""The seller the client sign in owns: a listed 3 BHK with a signed Exclusive mandate and four enquiries."""
	city = demo_names.REGIONS[region]["city"]
	locality = LOCALITIES[region][0]
	building = "Kesar Residency"
	return {
		"name": name,
		"email": email,
		"phone_seed": SEEDS["client"],
		"city": city,
		"property": {
			"title": f"3 BHK, {building}, {locality}",
			"property_type": "Apartment",
			"building_name": building,
			"city": city,
			"locality": locality,
			"address": f"{building}, {locality}, {city}",
			"configuration": "3 BHK",
			"carpet_area": 1180,
			"floor": 11,
			"parking": 2,
		},
		"stage": "Listed",
		"source": "Referral",
		"agent_index": 0,
		"created_days": 75,
		"enquiries": 4,
		"lost_reason": "",
		"mandate": {
			"state": "signed",
			"mandate_type": "Exclusive",
			"term_months": 9,
			"fee_percent": 1.5,
			"start_days_ago": 45,
			"notes": [0, 1],
			"files": 2,
		},
	}


def _pan(rng, first, last, i):
	letters = (re.sub(r"[^A-Z]", "", last.upper()) + "XXX")[:3]
	owner = re.sub(r"[^A-Z]", "", first.upper())[:1] or "X"
	check = "ABCDEFGHJKLMNPRSTUVWXYZ"[(i * 7 + rng.randint(0, 9)) % 23]
	return f"{letters}F{owner}{rng.randint(1000, 9999)}{check}"


def _rera(region, i, rng):
	number = 90000 + i * 113 + rng.randint(0, 99)
	if region == "bom":
		return f"A518000{number:05d}"
	return f"PR/GJ/AHMEDABAD/AGENT/AG{number:05d}/{23 + i % 3}"


def firm_plan(rng, region, today, used, first_contact):
	"""The 12 channel partner firms. The first is the demo partner's own, approved. `first_contact` is the
	demo partner's name; the others are drawn."""
	first, last = first_contact.split(" ", 1)[0], first_contact.split(" ")[-1]
	statuses = list(FIRM_STATUSES[1:])
	rng.shuffle(statuses)
	statuses = [FIRM_STATUSES[0], *statuses]
	used.add(first_contact)
	contacts = [{"name": first_contact, "first": first, "last": last}]
	contacts += demo_names.people(rng, region, FIRMS - 1, used)
	taken = set()
	rows = []
	for i, (contact, status) in enumerate(zip(contacts, statuses, strict=True)):
		while True:
			other = demo_names.person(rng, region)["last"]
			suffix = FIRM_SUFFIXES[(i + rng.randint(0, 7)) % len(FIRM_SUFFIXES)]
			name = f"{contact['last']} & {other} {suffix}"
			if other != contact["last"] and name not in taken:
				taken.add(name)
				break
		rows.append(
			{
				"firm_name": name,
				"contact_person": contact["name"],
				"email": _email(contact["first"], contact["last"]),
				"status": status,
				"rera_number": _rera(region, i, rng),
				"pan": _pan(rng, contact["first"], contact["last"], i),
				"phone_seed": SEEDS["firm"] + i,
				"suspend_reason": rng.choice(SUSPEND_REASONS) if status == "suspended" else "",
			}
		)
	return rows


def registration_plan(rng, region, today, used, approved_firms):
	"""The 24 buyers the approved firms register, in all six statuses."""
	people = demo_names.people(rng, region, REGISTRATIONS, used)
	rows = []
	for i, (person, status) in enumerate(zip(people, REGISTRATION_STATUSES, strict=True)):
		low, high = DAYS_BY_REGISTRATION[status]
		config = rng.choice(CONFIGURATIONS)
		budget = rng.choice(("85 lakh", "1.1 crore", "1.4 crore", "1.8 crore", "2.4 crore", "3.2 crore"))
		rows.append(
			{
				"buyer_name": person["name"],
				"phone_seed": SEEDS["registration"] + i,
				"firm_index": i % approved_firms,
				"status": status,
				"days_ago": rng.randint(low, high),
				"project_index": rng.randrange(12),
				"agent_index": rng.randrange(4),
				"note": f"Wants a {config}, budget {budget}",
				"agreed": 0 if i % 9 == 4 else 1,
				"rejection": rng.choice(REJECTIONS) if status == "Rejected" else "",
			}
		)
	return rows


def deal_plan(rng, today):
	"""The deals, each with where it ends up:
	partner_unit (24): a unit sold with a partner firm, approved, one payout each in Due, Approved, Paid or
	On hold (6 of each); property_approved (2): a resale flat, approved, no partner; property_pending (3): a
	resale flat whose split waits for approval; booked (3): a unit booked, split pending; cancelled (2): a
	booking that was cancelled."""
	rows = []
	payouts = ("due", "approved", "paid", "hold")
	for i in range(24):
		payout = payouts[i % 4]
		rows.append(
			{
				"kind": "partner_unit",
				"payout": payout,
				"hold_from": "Approved" if i % 8 == 3 else "Due",
				"days_ago": rng.randint(30, 95) if payout == "paid" else rng.randint(3, 60),
				"partner_percent": rng.choice((20, 25, 30, 35, 40)),
				"company_percent": rng.choice((30, 40)),
				"price_factor": rng.choice((0.96, 0.97, 0.98, 1.0)),
				"reference": rng.randint(100000, 999999),
			}
		)
	for i in range(2):
		rows.append(_other_deal(rng, "property_approved", i, 0))
	for i in range(3):
		rows.append(_other_deal(rng, "property_pending", i, rng.choice((0, 25, 30))))
	for i in range(3):
		rows.append(_other_deal(rng, "booked", i, 0))
	for i in range(2):
		rows.append(_other_deal(rng, "cancelled", i, 0))
	return rows


def _other_deal(rng, kind, i, partner_percent):
	return {
		"kind": kind,
		"payout": None,
		"days_ago": rng.randint(2, 40),
		"partner_percent": partner_percent,
		"company_percent": rng.choice((30, 40)),
		"price_factor": rng.choice((0.95, 0.97, 1.0)),
		"reference": rng.randint(100000, 999999),
		"index": i,
	}


def split_percents(agent_company_partner):
	"""Agent, partner and company percent from a plan row's partner and company shares; they add to 100."""
	partner, company = agent_company_partner
	return 100 - partner - company, partner, company


def round_price(value):
	"""A believable agreed price: to the nearest ten thousand rupees."""
	return int(round(value, -4))


# --- the Frappe side ----------------------------------------------------------------------------------------


# A seller's expected price: the carpet area at a rate per square foot, by city, to the nearest lakh.
RATES = {"Mumbai": (24000, 46000), "Ahmedabad": (5200, 9400)}
# What the next follow up of an open seller is, by the seller's number: overdue, soon, later or none.
FOLLOW_UPS = (
	(-3, "Call back about the asking price"),
	(1, "Confirm the viewing with the owner"),
	(6, "Ask for the society papers"),
	None,
)
CLOSED_SELLER_STAGES = ("Sold", "Closed lost")


def expected_price(spec):
	"""The owner's asking price in rupees, in whole lakhs, from the property and the city. The same for a spec
	every time."""
	low, high = RATES.get(spec["city"], RATES["Mumbai"])
	rate = low + (spec["phone_seed"] * 7919) % (high - low)
	return round(spec["property"]["carpet_area"] * rate, -5)


def _seller_activity(lead, spec, agent, ctx):
	"""A call the agent logged some days ago, and the next follow up of a seller still open (see FOLLOW_UPS), so
	the Sellers list shows a last activity and a next follow up that is overdue, soon, later or not set."""
	from datetime import datetime, time

	import frappe

	if spec["stage"] not in CLOSED_SELLER_STAGES and spec["phone_seed"] % 5:
		ago = min(1 + spec["phone_seed"] % 11, max(1, spec["created_days"] - 1))
		at = datetime.combine(ctx.today - timedelta(days=ago), time(11 + spec["phone_seed"] % 6, 20))
		doc = frappe.get_doc(
			{
				"doctype": "Lead Activity",
				"lead": lead,
				"activity_type": "Call",
				"activity_date": at,
				"notes": "Spoke to the owner about the asking price and the viewing times.",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Lead Activity", doc.name, {"creation": at, "modified": at}, update_modified=False
		)
		ctx.count("created", "Lead Activity")
	follow = FOLLOW_UPS[spec["phone_seed"] % len(FOLLOW_UPS)]
	if follow and spec["stage"] not in CLOSED_SELLER_STAGES:
		due = datetime.combine(ctx.today + timedelta(days=follow[0]), time(10 + spec["phone_seed"] % 7, 30))
		doc = frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": lead,
				"title": follow[1],
				"due_at": due,
				"status": "Open",
				"assigned_to": agent,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		stamp = datetime.combine(ctx.today - timedelta(days=5 + spec["phone_seed"] % 9), time(9, 40))
		frappe.db.set_value(
			"Lead Task", doc.name, {"creation": stamp, "modified": stamp}, update_modified=False
		)
		ctx.count("created", "Lead Task")


def _as(email):
	from sellos.tests import ui_fixtures

	return ui_fixtures._as_user(email)


def _phone(seed):
	from sellos.tests import phones

	return phones.in_mobile(seed)


def build(ctx):
	"""Make the company's sellers and mandates, partner firms, deals and payouts, and the client sign in's own
	seller lead and shortlist. Runs as the Company Admin through the production methods."""
	rng, region = ctx.rng, ctx.word
	today = ctx.today
	admin = ctx.users["admin"]
	with _as(admin):
		firms = _build_partners(ctx, rng, region, today)
		_build_rates(ctx, firms)
		_build_shares(ctx, firms)
		_build_registrations(ctx, rng, region, today, firms)
		plan = seller_plan(rng, region, today, ctx.used_names)
		client_spec = client_seller_spec(rng, region, ctx.staff_names["client"], ctx.users["client"])
		taken = set()
		for spec in [*plan, client_spec]:
			_build_seller(ctx, spec, today, taken)
		_build_deals(ctx, rng, today, firms)
	_build_client_shortlist(ctx)


def _build_partners(ctx, rng, region, today):
	"""The 12 firms through the invitation, the contact person's details and the Company Admin's decision."""
	from unittest.mock import patch

	import frappe

	from sellos.access import partner_firms, users
	from sellos.tests.files import tiny_pdf_base64

	plan = firm_plan(rng, region, today, ctx.used_names, ctx.staff_names["partner"])
	plan[0]["email"] = ctx.users["partner"]
	made = []
	for i, spec in enumerate(plan):
		name = frappe.db.get_value("Channel Partner Firm", {"firm_name": spec["firm_name"]}, "name")
		if not name:
			name = _make_firm(ctx, spec, i == 0, partner_firms, users, tiny_pdf_base64, patch)
			ctx.count("created", "Channel Partner Firm")
		row = {
			"name": name,
			"firm": spec["firm_name"],
			"email": spec["email"],
			"user": spec["email"],
			"contact_person": spec["contact_person"],
			"status": frappe.db.get_value("Channel Partner Firm", name, "status"),
		}
		made.append(row)
		ctx.partners.append(row)
	return made


def _make_firm(ctx, spec, own, partner_firms, users, agreement, patch):
	import frappe

	if own:
		doc = frappe.get_doc(
			{
				"doctype": "Channel Partner Firm",
				"firm_name": spec["firm_name"],
				"contact_user": spec["email"],
				"contact_person": spec["contact_person"],
				"email": spec["email"],
			}
		).insert()
		name = doc.name
	else:
		with patch.object(users, "mail_ready", return_value=False):
			invited = partner_firms.invite_partner_firm(
				spec["firm_name"], spec["contact_person"], spec["email"]
			)
		name = invited["name"]
	if spec["status"] != "invited":
		with _as(spec["email"]):
			partner_firms.submit_partner_details(
				{"phone": _phone(spec["phone_seed"]), "rera_number": spec["rera_number"], "pan": spec["pan"]}
			)
			partner_firms.upload_my_agreement("partner_agreement_signed.pdf", agreement())
	if spec["status"] in ("approved", "suspended"):
		partner_firms.approve_partner_firm(name)
	if spec["status"] == "suspended":
		partner_firms.suspend_partner_firm(name, spec["suspend_reason"])
	return name


def _build_rates(ctx, firms):
	"""A commission rate for each project, and a few firms with their own rate (the firm's beats the project's)."""
	import frappe

	from sellos.inventory import commissions

	approved = [f for f in firms if f["status"] == "Approved"]
	for i, project in enumerate(ctx.projects):
		if not frappe.db.exists(
			"Commission Rate", {"project": project["name"], "partner_firm": ["is", "not set"], "archived": 0}
		):
			commissions.save_commission_rate(
				{
					"project": project["name"],
					"rate_type": "Percentage",
					"value": PROJECT_RATES[i % len(PROJECT_RATES)],
					"start_date": "2025-01-01",
				}
			)
			ctx.count("created", "Commission Rate")
	for k, firm in enumerate(approved[1:4], start=1):
		project = ctx.projects[(k * 3) % len(ctx.projects)]["name"]
		if not frappe.db.exists("Commission Rate", {"project": project, "partner_firm": firm["name"]}):
			commissions.save_commission_rate(
				{
					"project": project,
					"partner_firm": firm["name"],
					"rate_type": "Percentage",
					"value": 3,
					"start_date": "2025-06-01",
				}
			)
			ctx.count("created", "Commission Rate")
	if len(approved) > 4:
		project = ctx.projects[0]["name"]
		if not frappe.db.exists("Commission Rate", {"project": project, "partner_firm": approved[4]["name"]}):
			commissions.save_commission_rate(
				{
					"project": project,
					"partner_firm": approved[4]["name"],
					"rate_type": "Fixed amount",
					"value": 250000,
					"start_date": "2025-06-01",
				}
			)
			ctx.count("created", "Commission Rate")


def _build_shares(ctx, firms):
	"""What the Company Admin shares with partners: the first project with every Approved firm (and its price
	list), the next ones with one or two firms each. Through the sharing method; a project already shared is
	left alone, so the seed can run again."""
	import frappe

	from sellos.inventory import partner_shares

	approved = [f["name"] for f in firms if f["status"] == "Approved"]
	if not approved:
		return
	for i, project in enumerate(ctx.projects[:4]):
		if frappe.db.exists("Partner Share", {"project": project["name"]}):
			continue
		targets = "all" if i == 0 else approved[i - 1 : i + 1] or approved[:1]
		partner_shares.share_project(project["name"], targets, share_price_list=1 if i % 2 == 0 else 0)
		ctx.count("created", "Partner Share")


def _build_registrations(ctx, rng, region, today, firms):
	"""The buyers the approved firms register, taken to every status through the production methods."""
	import frappe
	from frappe.utils import add_days, get_datetime, now_datetime

	from sellos.access import partner_registrations as pr
	from sellos.crm import api as crm
	from sellos.crm import pipeline

	approved = [f for f in firms if f["status"] == "Approved"]
	plan = registration_plan(rng, region, today, ctx.used_names, len(approved))
	agents = list(ctx.users["agents"])
	protection = pr.protection_days()
	projects = [frappe.db.get_value("Project", p["name"], "project_name") for p in ctx.projects]
	stage_of = {
		"Approved": pipeline.CONTACTED,
		"Visited": pipeline.SITE_VISIT_DONE,
		"Booked": pipeline.BOOKING,
		"Expired": pipeline.NURTURE,
	}
	for spec in plan:
		if frappe.db.exists("Partner Registration", {"buyer_name": spec["buyer_name"]}):
			continue
		firm = approved[spec["firm_index"]]
		status, days = spec["status"], spec["days_ago"]
		if status == "Expired":
			days = max(days, protection + 15)
		elif status in ("Approved", "Visited", "Booked"):
			days = min(days, max(protection - 10, 2))
		with _as(firm["user"]):
			result = pr.register_buyer(
				spec["buyer_name"],
				_phone(spec["phone_seed"]),
				projects[spec["project_index"] % len(projects)] if projects else "",
				spec["note"],
				spec["agreed"],
			)
		if not result.get("accepted"):
			raise RuntimeError(f"demo seed: the registration of {spec['buyer_name']} was not accepted")
		code = result["registration"]["name"]
		reg = frappe.get_doc("Partner Registration", code)
		lead = reg.lead
		if status == "Rejected":
			pr.reject_partner_registration(code, spec["rejection"])
		elif status != "Registered":
			pr.approve_partner_registration(code)
			if status == "Visited":
				pr.mark_visited(lead)
			elif status == "Booked":
				pr.mark_booked(lead)
			elif status == "Expired":
				frappe.get_doc("Partner Registration", code).change_status(
					"Expired", "The protection window ended without a booking."
				)
			crm.save_lead(name=lead, values={"assigned_to": agents[spec["agent_index"]]})
			crm.move_lead_stage(lead, stage_of[status])
		registered = add_days(now_datetime(), -days)
		changes = {"registered_on": registered}
		if status not in ("Registered", "Rejected"):
			changes["approved_on"] = add_days(registered, 1)
			changes["protected_until"] = add_days(get_datetime(changes["approved_on"]), protection)
		frappe.db.set_value("Partner Registration", code, changes, update_modified=False)
		frappe.db.set_value("Lead", lead, "creation", registered, update_modified=False)
		ctx.count("created", "Partner Registration")


def _enquiry_pool(ctx):
	"""Buyer leads that may become enquiries on a seller's property: not in a stage the deals use."""
	skip = {"Negotiation", "Booking", "Closed won", "Closed lost", "Nurture", "New", "Consent pending"}
	return [row for row in ctx.leads if row["stage"] not in skip and row.get("client")]


def _build_seller(ctx, spec, today, taken):
	"""One seller: client, own property, Seller lead, mandate with its dossier, and the enquiries on the property."""
	import base64

	import frappe
	from frappe.utils import add_days, now_datetime

	from sellos.crm import api as crm
	from sellos.crm import pipeline
	from sellos.inventory import api as inventory
	from sellos.inventory import mandates
	from sellos.tests.files import tiny_pdf

	pdf = base64.b64encode(tiny_pdf()).decode()
	agents = list(ctx.users["agents"])
	agent = agents[spec["agent_index"]]
	client = frappe.db.get_value("Client", {"email": spec["email"]}, "name")
	if not client:
		client = crm.save_client(
			values={
				"client_name": spec["name"],
				"client_type": "Seller",
				"phone": _phone(spec["phone_seed"]),
				"email": spec["email"],
				"city": spec["city"],
			}
		)["name"]
		ctx.count("created", "Client")
	title = spec["property"]["title"]
	prop = frappe.db.get_value("Property", {"title": title}, "name")
	if not prop:
		prop = inventory.save_property(spec["property"])["name"]
		ctx.count("created", "Property")
	lead = frappe.db.get_value("Lead", {"client": client, "pipeline": "Seller"}, "name")
	made = False
	if not lead:
		lead = crm.save_lead(
			values={
				"client": client,
				"pipeline": "Seller",
				"source": spec["source"],
				"assigned_to": agent,
				"property": prop,
				"budget_to": expected_price(spec),
				"notes": f"Owner of {title}. Wants to sell.",
			}
		)["lead"]["name"]
		made = True
		ctx.count("created", "Lead")
	m = spec["mandate"]
	mandate = frappe.db.get_value("Mandate", {"lead": lead}, "name")
	if not mandate:
		start = today - timedelta(days=m["start_days_ago"])
		mandate = mandates.save_mandate(
			{
				"lead": lead,
				"mandate_type": m["mandate_type"],
				"start_date": str(start),
				"term_months": m["term_months"],
				"fee_percent": m["fee_percent"],
			}
		)["name"]
		ctx.count("created", "Mandate")
		for index in m["notes"]:
			note_title, note = DOSSIER_NOTES[index]
			mandates.add_dossier_note(mandate, note_title, note)
		if m["state"] != "draft":
			for file_title, filename in DOSSIER_FILES[: m["files"]]:
				mandates.add_dossier_file(mandate, file_title, filename, pdf)
			mandates.sign_mandate(mandate, "mandate_signed.pdf", pdf)
			signed_on = add_days(now_datetime(), -m["start_days_ago"])
			frappe.db.set_value("Mandate", mandate, "signed_on", signed_on, update_modified=False)
			if m["state"] in ("signed", "archived"):
				with _as(agent):
					mandates.open_dossier(mandate)
	if made:
		stage = pipeline.stage_doc_name(pipeline.SELLER, spec["stage"])
		crm.move_lead_stage(lead, stage, lost_reason=spec["lost_reason"] or None)
		if spec["stage"] == "Sold":
			inventory.set_inventory_status("Property", prop, "Sold", "Sold through the company")
		frappe.db.set_value(
			"Lead", lead, "creation", add_days(now_datetime(), -spec["created_days"]), update_modified=False
		)
		_seller_activity(lead, spec, agent, ctx)
	if m["state"] == "archived" and not frappe.db.get_value("Mandate", mandate, "archived"):
		mandates.set_mandate_archived(mandate, 1)
	_add_enquiries(ctx, spec, prop, taken)
	state = frappe.db.get_value("Mandate", mandate, ["status", "archived"], as_dict=True)
	ctx.sellers.append(
		{
			"name": lead,
			"client": client,
			"client_name": spec["name"],
			"property": prop,
			"stage": spec["stage"],
			"agent": agent,
		}
	)
	ctx.mandates.append(
		{
			"name": mandate,
			"lead": lead,
			"status": state.status,
			"mandate_type": m["mandate_type"],
			"state": m["state"],
			"archived": bool(state.archived),
		}
	)


def _add_enquiries(ctx, spec, prop, taken):
	"""Buyer leads that asked about the seller's property, so the owner's page lists its enquiries."""
	import frappe

	from sellos.crm import api as crm

	have = frappe.db.count("Lead", {"property": prop, "pipeline": "Buyer"})
	need = spec["enquiries"] - have
	for row in _enquiry_pool(ctx):
		if need <= 0:
			break
		if row["name"] in taken or frappe.db.get_value("Lead", row["name"], "property"):
			continue
		taken.add(row["name"])
		crm.save_lead(name=row["name"], values={"property": prop})
		need -= 1


def _available_units(ctx):
	"""Available units of the demo projects in a steady order, each with its price from the inventory builder."""
	import frappe

	projects = {p["name"] for p in ctx.projects}
	price = {u["name"]: u.get("price") for u in ctx.units}
	rows = frappe.get_all(
		"Unit",
		filters={"status": "Available", "archived": 0, "project": ["in", sorted(projects)]},
		fields=["name", "project"],
		order_by="name asc",
	)
	return [{**r, "price": price.get(r.name)} for r in rows]


def _spread(rng, units):
	"""The units shuffled, then dealt out project by project so the deals touch many projects."""
	by_project = {}
	for unit in units:
		by_project.setdefault(unit["project"], []).append(unit)
	for rows in by_project.values():
		rng.shuffle(rows)
	order = []
	while any(by_project.values()):
		for project in sorted(by_project):
			if by_project[project]:
				order.append(by_project[project].pop())
	return order


class _Leads:
	"""Hands out the buyer leads of the demo's deals by stage, each lead once, never one that has a deal."""

	def __init__(self, ctx):
		import frappe

		self.rows = list(ctx.leads)
		self.used = set(frappe.get_all("Deal", filters={"lead": ["is", "set"]}, pluck="lead"))
		self.agents = list(ctx.users["agents"])
		self.turn = 0

	def take(self, *stages):
		for stage in stages:
			for row in self.rows:
				if row["stage"] == stage and row["name"] not in self.used and row.get("client"):
					self.used.add(row["name"])
					return row
		raise RuntimeError(f"demo seed: no lead left in {', '.join(stages)} for a deal")

	def agent_of(self, row):
		self.turn += 1
		agent = row.get("agent")
		return agent if agent in self.agents else self.agents[self.turn % len(self.agents)]


def _build_deals(ctx, rng, today, firms):
	"""The deals of every kind, each for a client whose lead is at a stage that fits it, then the context lists."""
	import frappe

	from sellos.crm import pipeline

	approved = [f for f in firms if f["status"] == "Approved"]
	plan = deal_plan(rng, today)
	leads = _Leads(ctx)
	units = _spread(rng, _available_units(ctx))
	properties = [
		p
		for p in ctx.properties
		if frappe.db.get_value("Property", p["name"], ["status", "archived"]) == ("Available", 0)
	]
	if frappe.db.count("Deal") >= len(plan):
		_report_deals(ctx)
		return
	# Bookings first: they need Booking stage leads, which the other deals may also use.
	order = sorted(range(len(plan)), key=lambda n: plan[n]["kind"] not in ("booked", "cancelled"))
	for i in order:
		spec = plan[i]
		kind = spec["kind"]
		if kind in ("booked", "cancelled"):
			stages = (pipeline.BOOKING, pipeline.SITE_VISIT_DONE, pipeline.NEGOTIATION)
		elif kind == "property_pending":
			stages = (
				pipeline.NEGOTIATION,
				pipeline.CLOSED_WON,
				pipeline.BOOKING,
				pipeline.SITE_VISIT_DONE,
			)
		else:
			stages = (
				pipeline.CLOSED_WON,
				pipeline.NEGOTIATION,
				pipeline.BOOKING,
				pipeline.SITE_VISIT_DONE,
			)
		if frappe.db.count("Deal") >= len(plan):
			break
		row = leads.take(*stages)
		if not (properties if kind.startswith("property") else units):
			raise RuntimeError(f"demo seed: no Available unit or property is left for a {kind} deal")
		firm = approved[i % len(approved)]
		deal_date = today - timedelta(days=spec["days_ago"])
		_make_deal(ctx, spec, row, leads.agent_of(row), firm, units, properties, deal_date)
		ctx.count("created", "Deal")
	_report_deals(ctx)


def _report_deals(ctx):
	"""Put every deal and payout of the site on the context (a second run creates none, but reports all)."""
	import frappe

	ctx.deals.clear()
	ctx.payouts.clear()
	for name in frappe.get_all("Deal", pluck="name", order_by="creation asc"):
		d = frappe.db.get_value(
			"Deal",
			name,
			["client", "lead", "unit", "property", "price", "approval_status", "deal_status"],
			as_dict=True,
		)
		split = frappe.get_all(
			"Commission Split", filters={"parent": name}, fields=["party_type", "agent", "partner_firm"]
		)
		d.update(
			agent=next((s.agent for s in split if s.party_type == "Agent"), None),
			partner_firm=next((s.partner_firm for s in split if s.party_type == "Channel Partner"), None),
		)
		ctx.deals.append({"name": name, **d})
	for p in frappe.get_all(
		"Commission Payout", fields=["name", "deal", "partner_firm", "status"], order_by="creation asc"
	):
		ctx.payouts.append(dict(p))


def _splits(agent, firm, percents):
	agent_percent, partner, company = percents
	rows = [{"party_type": "Agent", "agent": agent, "percent": agent_percent}]
	if partner:
		rows.append({"party_type": "Channel Partner", "partner_firm": firm, "percent": partner})
	rows.append({"party_type": "Company", "percent": company})
	return rows


def _make_deal(ctx, spec, row, agent, firm, units, properties, deal_date):
	"""One deal through the booking or deal methods, then its approval, the sold unit and its payout."""
	import frappe

	from sellos.access import partner_registrations
	from sellos.inventory import api as inventory
	from sellos.inventory import bookings, commissions, deals

	kind, lead = spec["kind"], row["name"]
	if kind in ("booked", "cancelled"):
		unit = units.pop()
		price = round_price((unit["price"] or 12000000) * spec["price_factor"])
		name = bookings.book(lead, unit["name"], price, round_price(price * 0.1))["deal"]
		if kind == "cancelled":
			bookings.cancel(name, CANCEL_REASONS[spec["index"] % len(CANCEL_REASONS)])
		return
	if kind == "partner_unit":
		unit = units.pop()
		price = round_price((unit["price"] or 12000000) * spec["price_factor"])
		rate = commissions.rate_in_force(unit["project"], firm["name"], deal_date)
		commission = float(commissions.commission_at_rate(price, rate)) if rate else round(price * 0.02)
		target = {"unit": unit["name"]}
		percents = split_percents((spec["partner_percent"], spec["company_percent"]))
	else:
		prop = properties.pop()
		price = round_price((prop.get("asking_price") or 15000000) * spec["price_factor"])
		commission = round(price * 0.02)
		target = {"property": prop["name"]}
		percents = (60, 0, 40)
		if kind == "property_pending" and spec["partner_percent"]:
			percents = split_percents((spec["partner_percent"], spec["company_percent"]))
	name = deals.save_deal(
		{
			"client": row["client"],
			"lead": lead,
			**target,
			"price": price,
			"deal_date": str(deal_date),
			"commission_amount": commission,
			"splits": _splits(agent, firm["name"], percents),
		}
	)["name"]
	if kind == "property_pending":
		return
	deals.approve_splits(name)
	if "unit" in target:
		inventory.set_inventory_status("Unit", target["unit"], "Sold", "Sold through the deal")
		frappe.db.set_value(
			"Deal",
			name,
			{"booking_amount": round_price(price * 0.1), "booked_by": ctx.users["admin"]},
			update_modified=False,
		)
	else:
		inventory.set_inventory_status("Property", target["property"], "Sold", "Sold through the deal")
	if kind == "partner_unit":
		if lead:
			partner_registrations.change_lead_partner(lead, firm["name"])
		_move_payout(ctx, name, firm["name"], spec, deal_date)
		ctx.count("created", "Commission Payout")


def _move_payout(ctx, deal, firm, spec, deal_date):
	"""Take the deal's Due payout to where the plan says: Approved, Paid with its reference, or On hold."""
	import frappe

	from sellos.inventory import commissions

	name = frappe.db.get_value("Commission Payout", {"deal": deal, "partner_firm": firm})
	if not name:
		raise RuntimeError(f"demo seed: deal {deal} made no payout for {firm}: no commission rate in force")
	target = spec["payout"]
	if target in ("approved", "paid") or (target == "hold" and spec["hold_from"] == "Approved"):
		commissions.move_payout(name, "Approved")
	if target == "paid":
		paid_on = min(deal_date + timedelta(days=9), ctx.today - timedelta(days=1))
		commissions.move_payout(
			name,
			"Paid",
			payment_reference=f"UTR{deal_date:%y%m%d}{spec['reference']}",
			paid_on=str(paid_on),
		)
	if target == "hold":
		commissions.move_payout(name, "On hold", reason=HOLD_REASONS[spec["reference"] % len(HOLD_REASONS)])


def _build_client_shortlist(ctx):
	"""The client sign in gets a Buyer lead (when it has none) and two shortlists: one shared, one a draft."""
	from unittest.mock import patch

	import frappe

	from sellos.access import users
	from sellos.crm import api as crm
	from sellos.inventory import shortlists

	agent = ctx.users["agents"][0]
	client = frappe.db.get_value("Client", {"email": ctx.users["client"]}, "name")
	if not client:
		raise RuntimeError("demo seed: the client sign in has no client record")
	title = "Homes chosen for you"
	if frappe.db.exists("Shortlist", {"client": client, "title": title}):
		return
	lead = frappe.db.get_value("Lead", {"client": client, "pipeline": "Buyer"}, "name")
	with _as(ctx.users["admin"]):
		if not lead:
			lead = crm.save_lead(
				values={
					"client": client,
					"source": "Website",
					"assigned_to": agent,
					"configuration": "3 BHK",
					"notes": "Looking for a larger home near the family.",
				}
			)["lead"]["name"]
			crm.move_lead_stage(lead, "Qualified")
			ctx.count("created", "Lead")
		else:
			crm.save_lead(name=lead, values={"assigned_to": agent})
	units = _available_units(ctx)
	if len(units) < 6:
		raise RuntimeError("demo seed: too few Available units for the client's shortlist")
	first_project = units[0]["project"]
	same = [u for u in units if u["project"] == first_project]
	chosen = (same + [u for u in units if u["project"] != first_project])[:4]
	listings = [row["name"] for row in ctx.listings if isinstance(row, dict) and row.get("name")][:2]
	with _as(agent), patch.object(users, "mail_ready", return_value=False):
		note = "Four homes I think suit your family."
		main = shortlists.create_shortlist(lead=lead, title=title, note=note)
		for unit in chosen:
			shortlists.add_to_shortlist("Unit", unit["name"], shortlist=main["name"])
		for listing in listings:
			try:
				shortlists.add_to_shortlist("Listing", listing, shortlist=main["name"])
			except frappe.ValidationError:
				pass  # a listing that is not offerable is left off
		items = shortlists.get_shortlist(main["name"])["items"]
		shortlists.save_item_note(main["name"], items[0]["name"], "Corner home, quiet side of the tower")
		shortlists.share_shortlist(main["name"], "Link")
		draft = shortlists.create_shortlist(lead=lead, title="Second look", note="To visit on Saturday.")
		shortlists.add_to_shortlist("Unit", chosen[-1]["name"], shortlist=draft["name"])
	ctx.count("created", "Shortlist", 2)
