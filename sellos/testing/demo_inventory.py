"""The demo seed's inventory builder: developers, projects with towers and units, price lists and payment
plans, resale properties and published listings, for one company site (demo seed).

The pure generators at the top take a random generator, a region key ("bom" or "amd") and today's date and
return plain dicts, so a unit test checks them without a bench (sellos/testing/test_demo_inventory.py). `build`
makes the records through the production inventory methods; it looks every record up first, so a second run
creates nothing. `hold_and_sell` runs after the crm builder, because a hold belongs to a lead.

Everything here is made up: the developers, the projects, the societies and the RERA numbers. A phone number
is never written here.
"""

import random
from datetime import date, timedelta

from sellos.testing import demo_names

# region -> [(locality, base rate in rupees per sq ft of carpet area, tier)] in the order the projects use them
LOCALITIES = {
	"bom": (
		("Andheri West", 32000, "premium"),
		("Powai", 28000, "mid"),
		("Bandra East", 38000, "premium"),
		("Worli", 62000, "premium"),
		("Thane", 15000, "value"),
		("Mulund", 19500, "mid"),
		("Chembur", 24500, "mid"),
		("Goregaon", 22500, "mid"),
		("Borivali", 19000, "mid"),
		("Navi Mumbai", 12500, "value"),
	),
	"amd": (
		("SG Highway", 7800, "premium"),
		("Prahlad Nagar", 7600, "premium"),
		("Bopal", 5600, "mid"),
		("Shela", 5200, "value"),
		("Gota", 4800, "value"),
		("Satellite", 7000, "mid"),
		("Thaltej", 8200, "premium"),
		("Vastrapur", 8000, "premium"),
		("South Bopal", 5300, "value"),
		("Science City", 6200, "mid"),
	),
}

DEVELOPERS = {
	"bom": (
		"Sankalp Meridian Developers",
		"Tarangan Realty",
		"Ashvika Group",
		"Nilgiri Shore Homes",
		"Kaustubh Estates",
		"Mandar Crest Builders",
	),
	"amd": (
		"Anantara Landmarks",
		"Sabarmati Crest Developers",
		"Vihaan Spaces",
		"Kshitij Habitat",
		"Rudraksh Hearth Developers",
		"Tapovan Realty",
	),
}

PROJECT_NAMES = {
	"bom": (
		"Saptarishi Heights",
		"Kalindi Greens",
		"Aranya Skyline",
		"Tulsi Vihar Residences",
		"Marine Crest",
		"Nandanvan Towers",
		"Sagarika Bay",
		"Ambrosia Park",
		"Shivalik Orchid",
		"Moonstone Residency",
		"Varsha Meadows",
		"Jaladhi Court",
	),
	"amd": (
		"Anand Sarovar",
		"Sabarmati Skyview",
		"Kesar Greens",
		"Vrindavan Elite",
		"Shreenath Horizon",
		"Tapovan Heights",
		"Mogra Residency",
		"Aaradhya Pinnacle",
		"Ranchhod Park",
		"Gulmohar Crest",
		"Navkar Enclave",
		"Saffron Meadows",
	),
}

AMENITIES = (
	"Swimming pool",
	"Gym",
	"Clubhouse",
	"Children's play area",
	"Jogging track",
	"Indoor games room",
	"Landscaped garden",
	"Power backup",
	"Visitor parking",
	"CCTV security",
	"Yoga deck",
	"Multipurpose hall",
	"Senior citizen corner",
	"EV charging",
	"Rainwater harvesting",
)

STREETS = (
	"Plot 12, Link Road",
	"Survey 214, Main Road",
	"Near the metro station",
	"Plot 7, Station Road",
	"Opposite the garden",
	"Plot 31, Service Road",
)

# (towers, floors, units per floor): every layout gives 60 units or more.
LAYOUTS = (
	(1, 16, 4),
	(2, 9, 4),
	(1, 14, 5),
	(2, 6, 6),
	(1, 12, 6),
	(2, 8, 4),
	(3, 5, 4),
	(1, 15, 4),
	(2, 10, 3),
	(1, 20, 3),
	(3, 6, 4),
	(2, 7, 5),
)
READY_TO_MOVE = (
	1,
	3,
	5,
	8,
	10,
)  # indexes of the projects that are ready to move; the others are under construction

CONFIG_ORDER = ("1 BHK", "2 BHK", "3 BHK", "4 BHK")
TIER_WEIGHTS = {
	"premium": {"2 BHK": 2, "3 BHK": 5, "4 BHK": 2},
	"mid": {"1 BHK": 1, "2 BHK": 5, "3 BHK": 3},
	"value": {"1 BHK": 3, "2 BHK": 5, "3 BHK": 1},
}
FORCED = {"premium": "4 BHK", "mid": None, "value": "1 BHK"}
BASE_AREA = {
	"bom": {"1 BHK": 410, "2 BHK": 650, "3 BHK": 930, "4 BHK": 1350},
	"amd": {"1 BHK": 620, "2 BHK": 950, "3 BHK": 1350, "4 BHK": 1900},
}
PARKING = {
	"bom": {"1 BHK": 0, "2 BHK": 1, "3 BHK": 2, "4 BHK": 3},
	"amd": {"1 BHK": 1, "2 BHK": 1, "3 BHK": 2, "4 BHK": 3},
}
# The stamp duty, registration and GST percentages of each region's cost sheets.
COST_RATES = {"bom": (6, 1, 5), "amd": (4.9, 1, 5)}

SOCIETY_PREFIX = {
	"bom": (
		"Sagar",
		"Shanti",
		"Om",
		"Anand",
		"Kailash",
		"Gokul",
		"Ganga",
		"Sai",
		"Swapna",
		"Pushpa",
		"Lakshmi",
		"Vijay",
		"Mangal",
		"Surya",
		"Dev",
		"Neelam",
		"Chandan",
		"Rajhans",
		"Krishna",
		"Madhuri",
	),
	"amd": (
		"Shreeji",
		"Swaminarayan",
		"Kalash",
		"Aashirwad",
		"Satyam",
		"Shivam",
		"Rajvi",
		"Siddhi",
		"Vandana",
		"Aarohi",
		"Parshwa",
		"Mangalam",
		"Dhara",
		"Suvarna",
		"Nilkanth",
		"Harmony",
		"Madhav",
		"Pratham",
		"Vishwas",
		"Yash",
	),
}
SOCIETY_SUFFIX = {
	"bom": ("Darshan CHS", "Niwas", "Apartments", "Heights CHS", "Residency", "Co-op Housing Society"),
	"amd": ("Residency", "Apartments", "Flats", "Park", "Tower", "Society"),
}


def _round(value, step):
	return int(round(value / step) * step)


def _slug(text):
	return "".join(c for c in text.lower() if c.isalnum())


def _rera(rng, region, used, when):
	"""A made up RERA number in the region's format: MahaRERA `P518000` plus five digits, or a Gujarat
	`PR/GJ/AHMEDABAD/...` number. Never a real one: the digits are drawn."""
	while True:
		digits = f"{rng.randrange(100000):05d}"
		if region == "bom":
			number = f"P518000{digits}"
		else:
			number = f"PR/GJ/AHMEDABAD/AUDA/RAA{digits}/{when:%d%m%y}"
		if number not in used:
			used.add(number)
			return number


def make_developers(rng, region, used_names=None):
	"""Six developers with a contact person and an example.com email."""
	people = demo_names.people(rng, region, len(DEVELOPERS[region]), used_names)
	out = []
	for name, person in zip(DEVELOPERS[region], people, strict=True):
		slug = _slug(name)
		out.append(
			{
				"developer_name": name,
				"contact_person": person["name"],
				"email": f"sales@{slug}.example.com",
				"website": f"https://www.{slug}.example.com",
				"notes": f"Builds in {demo_names.REGIONS[region]['city']} and its suburbs.",
			}
		)
	return out


def _stack(rng, region, tier, per_floor, factor):
	"""The units of one floor, smallest first: [{configuration, carpet_area, parking, count}]."""
	weights = TIER_WEIGHTS[tier]
	configs = rng.choices(list(weights), weights=list(weights.values()), k=per_floor)
	forced = FORCED[tier]
	if forced and forced not in configs:
		configs[rng.randrange(per_floor)] = forced
	if len(set(configs)) < 2:
		configs[0] = "2 BHK" if configs[0] != "2 BHK" else "3 BHK"
	configs.sort(key=CONFIG_ORDER.index)
	groups = []
	for config in configs:
		if groups and groups[-1]["configuration"] == config:
			groups[-1]["count"] += 1
			continue
		groups.append(
			{
				"configuration": config,
				"carpet_area": _round(BASE_AREA[region][config] * factor, 5),
				"parking": PARKING[region][config],
				"count": 1,
			}
		)
	return groups


def _plan(rng, status):
	if status == "Ready to move":
		return {
			"plan_name": "Ready home 10:90",
			"plan_type": "Time linked",
			"instalments": [
				{"label": "Booking amount", "days_after_booking": 0, "percent": 10},
				{"label": "At agreement, 30 days after", "days_after_booking": 30, "percent": 90},
			],
		}
	stages = rng.choice(
		(
			(("On booking", 20), ("On the plinth", 30), ("On possession", 50)),
			(("On booking", 10), ("On the 4th slab", 20), ("On the 12th slab", 30), ("On possession", 40)),
			(("On booking", 15), ("On the top slab", 35), ("On possession", 50)),
		)
	)
	label = ":".join(str(p) for _, p in stages)
	return {
		"plan_name": f"Construction linked {label}",
		"plan_type": "Construction linked",
		"instalments": [{"label": s, "due_on": s, "percent": p} for s, p in stages],
	}


def _price_list(name, rate, region, floors, today):
	parking = _round(rate * (13 if region == "bom" else 28), 50000 if region == "bom" else 25000)
	return {
		"title": f"{name} price list {today.year}",
		"effective_from": str(today - timedelta(days=90)),
		"base_rate": rate,
		"floor_rise_rate": max(_round(rate * 0.004, 5), 5),
		"floor_rise_from_floor": 6,
		"charges": [
			{
				"charge_type": "Preferred location",
				"charge_name": "Garden facing",
				"basis": "Rate per sq ft",
				"value": max(_round(rate * 0.005, 10), 10),
			},
			{
				"charge_type": "Parking",
				"charge_name": "Covered parking",
				"basis": "Amount",
				"value": max(parking, 50000),
			},
			{
				"charge_type": "Other",
				"charge_name": "Development charges",
				"basis": "Amount",
				"value": 250000 if region == "bom" else 100000,
				"always_apply": 1,
			},
		],
	}


def make_projects(rng, region, today, developers):
	"""Twelve primary projects, each with towers, a floor stack, a price list and a payment plan."""
	localities = LOCALITIES[region]
	city = demo_names.REGIONS[region]["city"]
	used = set()
	out = []
	for i, name in enumerate(PROJECT_NAMES[region]):
		locality, base_rate, tier = localities[i % len(localities)]
		status = "Ready to move" if i in READY_TO_MOVE else "Under construction"
		rate = _round(base_rate * rng.uniform(0.92, 1.1), 100)
		tower_count, floors, per_floor = LAYOUTS[i]
		factor = rng.choice((0.96, 1.0, 1.04, 1.08)) * (1.05 if tier == "premium" else 1)
		stack = _stack(rng, region, tier, per_floor, factor)
		noun = "Tower" if tier == "premium" else "Wing"
		towers = [
			{
				"tower_name": f"{noun} {chr(65 + t)}",
				"prefix": f"{chr(65 + t)}-" if tower_count > 1 else "",
				"floors": floors,
				"stack": stack,
			}
			for t in range(tower_count)
		]
		if status == "Ready to move":
			possession = today - timedelta(days=30 * rng.randint(2, 30))
		else:
			possession = today + timedelta(days=30 * rng.randint(10, 40))
		out.append(
			{
				"project_name": name,
				"developer_name": developers[i % len(developers)]["developer_name"],
				"rera_number": _rera(rng, region, used, today),
				"city": city,
				"locality": locality,
				"address": f"{rng.choice(STREETS)}, {locality}, {city}",
				"project_status": status,
				"possession_date": str(possession),
				"rate": rate,
				"tier": tier,
				"amenities": rng.sample(AMENITIES, rng.randint(6, 9)),
				"towers": towers,
				"price_list": _price_list(name, rate, region, floors, today),
				"payment_plan": _plan(rng, status),
			}
		)
	return out


def tower_floor_groups(tower, floor):
	"""The unit pattern of one floor: [(pattern "101 to 102", carpet area, configuration, parking, prefix)]."""
	out, k = [], 1
	for group in tower["stack"]:
		first, last = floor * 100 + k, floor * 100 + k + group["count"] - 1
		out.append(
			(
				f"{first} to {last}",
				group["carpet_area"],
				group["configuration"],
				group["parking"],
				tower["prefix"],
			)
		)
		k += group["count"]
	return out


def project_units(project):
	"""Every unit of a project as a plain dict, price = rate x carpet area."""
	out = []
	for tower in project["towers"]:
		for floor in range(1, tower["floors"] + 1):
			k = 1
			for group in tower["stack"]:
				for _ in range(group["count"]):
					out.append(
						{
							"tower_name": tower["tower_name"],
							"floor": floor,
							"unit_number": f"{tower['prefix']}{floor * 100 + k}",
							"configuration": group["configuration"],
							"carpet_area": group["carpet_area"],
							"parking": group["parking"],
							"price": int(project["rate"] * group["carpet_area"]),
						}
					)
					k += 1
	return out


def make_properties(rng, region, today, count=40):
	"""Secondary (resale) properties, spread evenly over the ten localities."""
	localities = LOCALITIES[region]
	city = demo_names.REGIONS[region]["city"]
	prefixes, suffixes = SOCIETY_PREFIX[region], SOCIETY_SUFFIX[region]
	used_rera = set()
	out = []
	for i in range(count):
		locality, base_rate, tier = localities[i % len(localities)]
		society = f"{prefixes[i % len(prefixes)]} {suffixes[(i // len(prefixes)) * 3 + i % 3]}"
		age = rng.randint(2, 28)
		villa = region == "amd" and i % 8 == 7
		weights = TIER_WEIGHTS[tier]
		config = "Villa" if villa else rng.choices(list(weights), weights=list(weights.values()))[0]
		if villa:
			area = _round(rng.uniform(2200, 3000), 10)
			floor, parking, kind = None, 2, "Villa"
		else:
			area = _round(BASE_AREA[region][config] * rng.uniform(0.9, 1.0), 5)
			floor = rng.randint(1, 18)
			parking, kind = PARKING[region][config], "Apartment"
		resale_rate = base_rate * rng.uniform(0.78, 0.92) * (1 - min(age, 25) * 0.004)
		price = _round(resale_rate * area, 50000 if region == "bom" else 25000)
		title = f"{config} in {society}, {locality}"
		out.append(
			{
				"title": title,
				"property_type": kind,
				"building_name": society,
				"rera_number": _rera(rng, region, used_rera, today) if age <= 6 else "",
				"city": city,
				"locality": locality,
				"address": f"{rng.choice(STREETS)}, {locality}, {city}. Society built in {today.year - age}.",
				"configuration": config,
				"carpet_area": area,
				"floor": floor,
				"parking": parking,
				"age_years": age,
				"asking_price": price,
			}
		)
	return out


def plan_listings(rng, projects, properties, primary_projects=9, partner_count=6, direct_count=26):
	"""Which units and properties get a published listing:
	{"primary": [(project index, tower name, unit number)], "direct": [property index], "partner": [property index]}."""
	primary = []
	for index in sorted(rng.sample(range(len(projects)), primary_projects)):
		units = project_units(projects[index])
		floors = max(u["floor"] for u in units)
		pool = [
			u
			for u in units
			if 3 <= u["floor"] <= floors - 1 and u["configuration"] in ("2 BHK", "3 BHK", "4 BHK")
		] or units
		picked = {}
		for unit in rng.sample(pool, len(pool)):
			if unit["floor"] not in picked:
				picked[unit["floor"]] = unit
			if len(picked) == 2:
				break
		primary += [(index, u["tower_name"], u["unit_number"]) for u in picked.values()]
	order = rng.sample(range(len(properties)), partner_count + direct_count)
	return {
		"primary": primary,
		"partner": sorted(order[:partner_count]),
		"direct": sorted(order[partner_count:]),
	}


def primary_listing(project, unit):
	"""(title, description, asking price) of a primary listing."""
	title = (
		f"{unit['configuration']} {unit['unit_number']} at {project['project_name']}, {project['locality']}"
	)
	description = (
		f"{unit['configuration']} of {unit['carpet_area']:g} sq ft carpet area on floor {unit['floor']} at "
		f"{project['project_name']}, {project['locality']}. RERA {project['rera_number']}, "
		f"{project['project_status'].lower()}, with a payment plan to suit."
	)
	return title, description, unit["price"]


def property_listing(prop):
	"""(title, description, asking price) of a resale listing."""
	lift = "" if prop["property_type"] == "Villa" else " and a lift"
	description = (
		f"{prop['title']}. {prop['carpet_area']:g} sq ft carpet area, {prop['age_years']} year old building, "
		f"{prop['parking']} parking. Society with 24 hour security{lift}."
	)
	return prop["title"], description, prop["asking_price"]


# --- the Frappe side ---------------------------------------------------------------------------------


def build(ctx):
	"""Make this company's inventory and leave it on ctx.developers, projects, units, properties and listings."""
	import frappe

	from sellos.inventory import api, listings, pricing, structure
	from sellos.tests.ui_fixtures import _as_user

	rng = random.Random(f"demo inventory {ctx.word}")
	region, today = ctx.word, ctx.today
	admin, agent = ctx.users["admin"], ctx.users["agents"][0]
	developers = make_developers(rng, region, ctx.used_names)
	projects = make_projects(rng, region, today, developers)
	properties = make_properties(rng, region, today)
	plan = plan_listings(rng, projects, properties)

	with _as_user(admin):
		if pricing.cost_rates() is None:
			pricing.save_cost_settings(*COST_RATES[region])
			ctx.count("created", "Cost settings")
		known = {a for a in frappe.get_all("Amenity", pluck="name")}
		for amenity in AMENITIES:
			if amenity not in known:
				structure.save_amenity(amenity)
				ctx.count("created", "Amenity")
		for dev in developers:
			if not frappe.db.exists("Developer", dev["developer_name"]):
				api.save_developer(dev)
				ctx.count("created", "Developer")
			dev["name"] = frappe.db.exists("Developer", dev["developer_name"])
		ctx.developers[:] = developers
		for spec in projects:
			_build_project(ctx, spec, api, structure, pricing)

	_load_units(ctx, projects)
	with _as_user(agent):
		_build_properties(ctx, properties, api)
		_build_listings(ctx, projects, properties, plan, listings)


def _build_project(ctx, spec, api, structure, pricing):
	import frappe

	name = frappe.db.get_value("Project", {"project_name": spec["project_name"]}, "name")
	if not name:
		fields = ("project_name", "rera_number", "city", "locality", "address", "project_status")
		name = api.save_project(
			{**{k: spec[k] for k in fields}, "developer": _developer(spec["developer_name"])}
		)["name"]
		ctx.count("created", "Project")
	spec["name"] = name
	if not frappe.db.get_value("Project", name, "possession_date"):
		structure.save_project_details(name, spec["possession_date"], spec["amenities"])
	expected = len(project_units(spec))
	have = frappe.db.count("Unit", {"project": name})
	for tower in spec["towers"]:
		tower_id = frappe.db.get_value(
			"Project Tower", {"project": name, "tower_name": tower["tower_name"]}, "name"
		)
		if not tower_id:
			tower_id = structure.add_tower(name, tower["tower_name"], f"1 to {tower['floors']}")["name"]
			ctx.count("created", "Project Tower")
		tower["name"] = tower_id
		if have >= expected:
			continue
		for floor in range(1, tower["floors"] + 1):
			for pattern, area, config, parking, prefix in tower_floor_groups(tower, floor):
				made = structure.generate_floor_units(
					tower_id, floor, pattern, area, config, prefix=prefix, parking=parking
				)
				ctx.count("created", "Unit", len(made["created"]))
	if not frappe.db.exists("Price List", {"project": name}):
		pricing.save_price_list(name, spec["price_list"])
		ctx.count("created", "Price List")
	if not frappe.db.exists(
		"Payment Plan", {"project": name, "plan_name": spec["payment_plan"]["plan_name"]}
	):
		pricing.save_payment_plan(name, spec["payment_plan"])
		ctx.count("created", "Payment Plan")
	spec["payment_plan_name"] = frappe.db.get_value(
		"Payment Plan", {"project": name, "plan_name": spec["payment_plan"]["plan_name"]}, "name"
	)


def _developer(developer_name):
	import frappe

	return frappe.db.get_value("Developer", {"developer_name": developer_name}, "name")


def _load_units(ctx, projects):
	"""Read the made records back onto ctx.projects and ctx.units."""
	import frappe

	towers = {t.name: t.tower_name for t in frappe.get_all("Project Tower", fields=["name", "tower_name"])}
	ctx.projects[:] = []
	ctx.units[:] = []
	for spec in projects:
		rows = frappe.get_all(
			"Unit",
			filters={"project": spec["name"], "archived": 0},
			fields=[
				"name",
				"unit_number",
				"tower",
				"floor",
				"configuration",
				"carpet_area",
				"parking",
				"status",
			],
			order_by="tower, floor, unit_number",
		)
		project = {
			"name": spec["name"],
			"project_name": spec["project_name"],
			"developer": _developer(spec["developer_name"]),
			"developer_name": spec["developer_name"],
			"rera": spec["rera_number"],
			"city": spec["city"],
			"locality": spec["locality"],
			"status": spec["project_status"],
			"possession_date": spec["possession_date"],
			"rate": spec["rate"],
			"payment_plan": spec.get("payment_plan_name"),
			"units": [r.name for r in rows],
		}
		ctx.projects.append(project)
		for r in rows:
			ctx.units.append(
				{
					"name": r.name,
					"project": spec["name"],
					"project_name": spec["project_name"],
					"locality": spec["locality"],
					"number": r.unit_number,
					"tower": towers.get(r.tower, ""),
					"floor": r.floor,
					"configuration": r.configuration,
					"carpet_area": r.carpet_area,
					"parking": r.parking,
					"rate": spec["rate"],
					"price": int(spec["rate"] * r.carpet_area),
					"status": r.status,
				}
			)


def _build_properties(ctx, properties, api):
	import frappe

	fields = (
		"title",
		"property_type",
		"building_name",
		"rera_number",
		"configuration",
		"carpet_area",
		"floor",
		"parking",
		"city",
		"locality",
		"address",
	)
	ctx.properties[:] = []
	for prop in properties:
		name = frappe.db.get_value("Property", {"title": prop["title"]}, "name")
		if not name:
			values = {k: prop[k] for k in fields if prop[k] not in (None, "")}
			name = api.save_property(values)["name"]
			ctx.count("created", "Property")
		prop["name"] = name
		ctx.properties.append(
			{
				"name": name,
				"title": prop["title"],
				"locality": prop["locality"],
				"configuration": prop["configuration"],
				"carpet_area": prop["carpet_area"],
				"age_years": prop["age_years"],
				"building_name": prop["building_name"],
				"asking_price": prop["asking_price"],
				"status": frappe.db.get_value("Property", name, "status"),
			}
		)


def _build_listings(ctx, projects, properties, plan, listings):
	import frappe

	ctx.listings[:] = []
	by_project = {}
	for u in ctx.units:
		by_project.setdefault(u["project"], {})[(u["tower"], u["number"])] = u
	wanted = []
	for index, tower, number in plan["primary"]:
		spec = projects[index]
		unit = by_project[spec["name"]][(tower, number)]
		title, description, price = primary_listing(spec, {**unit, "unit_number": number})
		wanted.append(
			("Primary", title, description, price, {"unit": unit["name"]}, spec, unit["configuration"], unit)
		)
	for kind, indexes in (("Direct", plan["direct"]), ("Partner", plan["partner"])):
		for i in indexes:
			prop = properties[i]
			title, description, price = property_listing(prop)
			wanted.append(
				(
					kind,
					title,
					description,
					price,
					{"property": prop["name"]},
					None,
					prop["configuration"],
					prop,
				)
			)
	for kind, title, description, price, target, spec, configuration, record in wanted:
		row = frappe.db.get_value("Listing", {"title": title}, ["name", "published"], as_dict=True)
		if not row:
			name = listings.save_listing(
				{
					"title": title,
					"listing_type": kind,
					"asking_price": price,
					"description": description,
					**target,
				}
			)["name"]
			ctx.count("created", "Listing")
			row = frappe._dict(name=name, published=0)
		if not row.published:
			listings.publish_listing(row.name)
			ctx.count("published", "Listing")
		ctx.listings.append(
			{
				"name": row.name,
				"title": title,
				"listing_type": kind,
				"project": spec["name"] if spec else None,
				"locality": record["locality"],
				"configuration": configuration,
				"price": price,
				"status": "Published",
				**target,
			}
		)


def hold_and_sell(
	ctx, held_share=0.08, sold_ready=0.28, sold_building=0.14, properties_held=3, properties_sold=4
):
	"""Hold and sell some units and properties, after the crm builder has made the leads (ctx.leads).

	A hold needs a lead, so each held unit is held for a lead of its agent. A unit or property with a published
	listing is held but never sold, so a published listing never shows a sold home. Units a deal sells later are
	chosen by the sales builder from what is still Available (the status on ctx.units is kept current)."""
	import frappe

	from sellos.inventory import api, holds
	from sellos.tests.ui_fixtures import _as_user

	if not ctx.leads:
		raise ValueError("hold_and_sell needs ctx.leads: run the crm builder first")
	rng = random.Random(f"demo hold and sell {ctx.word}")
	admin = ctx.users["admin"]
	listed = {listing.get("unit") for listing in ctx.listings} | {
		listing.get("property") for listing in ctx.listings
	}
	live = {leadrow["name"]: leadrow for leadrow in ctx.leads}
	usable = [
		leadrow
		for leadrow in ctx.leads
		if not any(w in str(leadrow.get("stage", "")).lower() for w in ("lost", "won", "booked", "closed"))
	] or list(live.values())
	rng.shuffle(usable)
	agents = ctx.users["agents"]
	held = sold = 0
	for project in ctx.projects:
		units = [u for u in ctx.units if u["project"] == project["name"]]
		rng.shuffle(units)
		share = sold_ready if project["status"] == "Ready to move" else sold_building
		hold_n, sold_n = round(len(units) * held_share), round(len(units) * share)
		hold_units, sold_units = (
			units[:hold_n],
			[u for u in units[hold_n:] if u["name"] not in listed][:sold_n],
		)
		for unit in hold_units:
			if frappe.db.get_value("Unit", unit["name"], "status") != "Available" or not usable:
				unit["status"] = frappe.db.get_value("Unit", unit["name"], "status")
				continue
			lead = usable[held % len(usable)]
			holder = lead.get("agent") or agents[held % len(agents)]
			with _as_user(holder):
				holds.hold_unit_for(
					unit["name"], lead["name"], hours=24 * 14, reason="Held while the buyer decides"
				)
			unit["status"] = "Held"
			held += 1
		with _as_user(admin):
			for unit in sold_units:
				if frappe.db.get_value("Unit", unit["name"], "status") == "Available":
					api.set_inventory_status("Unit", unit["name"], "Sold", "Sold, agreement signed")
					sold += 1
				unit["status"] = frappe.db.get_value("Unit", unit["name"], "status")
	ctx.count("held", "Unit", held)
	ctx.count("sold", "Unit", sold)
	_move_properties(ctx, listed, rng, properties_held, properties_sold)


def _move_properties(ctx, listed, rng, held_n, sold_n):
	import frappe

	from sellos.inventory import api
	from sellos.tests.ui_fixtures import _as_user

	free = [p for p in ctx.properties if p["name"] not in listed]
	listed_props = [p for p in ctx.properties if p["name"] in listed]
	rng.shuffle(free)
	rng.shuffle(listed_props)
	with _as_user(ctx.users["admin"]):
		for props, status, count, reason in (
			(free, "Sold", sold_n, "Sold, agreement signed"),
			(listed_props, "Held", held_n, "Held for a buyer's second visit"),
		):
			for prop in props[:count]:
				if frappe.db.get_value("Property", prop["name"], "status") == "Available":
					api.set_inventory_status("Property", prop["name"], status, reason)
					ctx.count("sold" if status == "Sold" else "held", "Property")
				prop["status"] = frappe.db.get_value("Property", prop["name"], "status")
